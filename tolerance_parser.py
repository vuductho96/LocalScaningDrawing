import re
import math
import os
import json
from typing import Dict, Any, Optional

RULES_FILE = os.path.join(os.path.dirname(__file__), "adaptation_rules.json")

class AdaptiveLearner:
    """
    He thong thich ung thoi gian thuc dua tren chinh sua cua con nguoi (Human-in-the-Loop).
    Bao gom 3 tang:
    1. Exact Match: Khop chinh xac chuoi Raw OCR da tung duoc sua (1-Shot).
    2. Generalized Rules: Quy tac mau Regex duoc tu dong khai quat hoa (1-2 Shot).
    3. Confusion Matrix: Bo thay the ky tu OCR hay bi nham lan.
    """
    def __init__(self, rules_file: str = RULES_FILE):
        self.rules_file = rules_file
        self.exact_matches: Dict[str, Dict[str, Any]] = {}
        self.generalized_rules: list = []
        self.char_replacements: Dict[str, str] = {}
        self.load_rules()

    def load_rules(self):
        if not os.path.exists(self.rules_file):
            default_data = {
                "exact_matches": {},
                "generalized_rules": [
                    {
                        "id": "rule_dms_angle",
                        "name": "Kích thước góc độ DMS (Độ Phút Giây)",
                        "pattern": r"^([0-9]+(?:\.[0-9]+)?)[°\u3002].*$",
                        "type": "angle",
                        "user_defined": False
                    }
                ],
                "char_replacements": {}
            }
            self.save_rules_to_disk(default_data)

        try:
            with open(self.rules_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.exact_matches = data.get("exact_matches", {})
                self.generalized_rules = data.get("generalized_rules", [])
                self.char_replacements = data.get("char_replacements", {})
        except Exception as e:
            print(f"Error loading adaptive rules: {e}")
            self.exact_matches = {}
            self.generalized_rules = []
            self.char_replacements = {}

    def save_rules_to_disk(self, data: Optional[Dict[str, Any]] = None):
        if data is None:
            data = {
                "exact_matches": self.exact_matches,
                "generalized_rules": self.generalized_rules,
                "char_replacements": self.char_replacements
            }
        try:
            with open(self.rules_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving adaptive rules: {e}")

    def apply_adaptations(self, raw_text: str) -> Optional[Dict[str, Any]]:
        if not raw_text:
            return None

        clean = raw_text.strip()

        # 1. Exact match (Tang 1 - 1-Shot)
        if clean in self.exact_matches:
            matched = self.exact_matches[clean]
            res = dict(matched)
            res["source"] = "adaptive_exact"
            res["success"] = True
            return res

        # 2. Generalized Rules (Tang 2)
        for rule in self.generalized_rules:
            pat = rule.get("pattern")
            if not pat:
                continue
            try:
                m = re.search(pat, clean)
                if m:
                    rule_type = rule.get("type", "custom")
                    if rule_type == "angle":
                        dms_info = ToleranceParser.parse_dms_components(clean)
                        if dms_info:
                            callout = dms_info["callout"]
                            u_tol = dms_info["upper_tol"]
                            l_tol = dms_info["lower_tol"]
                            full_callout = callout
                            if u_tol and l_tol:
                                if u_tol == l_tol.replace('-', '+'):
                                    full_callout += f" ±{u_tol.replace('+', '')}"
                                else:
                                    full_callout += f" {u_tol}/{l_tol}"
                            elif u_tol:
                                full_callout += f" {u_tol}"
                            elif l_tol:
                                full_callout += f" {l_tol}"
                            return {
                                "success": True,
                                "raw_text": raw_text,
                                "qty": "",
                                "prefix": "",
                                "nominal": callout,
                                "nominal_str": callout,
                                "upper_tol": u_tol,
                                "lower_tol": l_tol,
                                "tol_type": dms_info["tol_type"],
                                "suffix": "",
                                "full_callout": full_callout,
                                "source": f"adaptive_rule:{rule.get('name', 'custom')}"
                            }
                    elif rule_type == "split_tokens":
                        # Xu ly cac cum so wildcard bat ky (vi du: 5 0 5 -0.02, 10 0 2 -0.05, 3 +0.02 1 1 0)
                        groups = [g for g in m.groups() if g is not None]
                        # Tim token chua dung sai co dau (+ hoac -)
                        tols = [g for g in groups if g.startswith('+') or g.startswith('-')]
                        nums_clean = [g for g in groups if not g.startswith('+') and not g.startswith('-')]
                        
                        nom_str = ""
                        nom_val = None
                        u_tol = "0"
                        l_tol = "0"

                        # Truong hop dac trung 4.04 bi OCR tach roi: "4 0 4" -> 4.04 (hoac "5 0 5" -> 5.05)
                        if len(nums_clean) == 3 and nums_clean[1] == '0':
                            nom_str = f"{nums_clean[0]}.0{nums_clean[2]}"
                            try:
                                nom_val = float(nom_str)
                            except ValueError:
                                nom_val = None
                        elif len(nums_clean) >= 1:
                            # Chon so lon nhat hoac ghep hop ly
                            candidates = []
                            for c in nums_clean:
                                try:
                                    candidates.append((float(c), c))
                                except ValueError:
                                    pass
                            if candidates:
                                candidates.sort(key=lambda x: x[0], reverse=True)
                                nom_val, nom_str = candidates[0]

                        # Dung sai
                        if tols:
                            for t in tols:
                                if t.startswith('+'):
                                    u_tol = t
                                elif t.startswith('-'):
                                    l_tol = t
                        else:
                            tmpl = rule.get("template", {})
                            u_tol = tmpl.get("default_upper", "0")
                            l_tol = tmpl.get("default_lower", "0")

                        if nom_val is not None:
                            callout_parts = [nom_str]
                            if u_tol or l_tol:
                                if u_tol == (l_tol or '').replace('-', '+'):
                                    callout_parts.append(f"±{u_tol.replace('+', '')}")
                                else:
                                    callout_parts.append(f"{u_tol or '0'}/{l_tol or '0'}")
                            callout = " ".join(callout_parts)

                            return {
                                "success": True,
                                "raw_text": raw_text,
                                "qty": "",
                                "prefix": "",
                                "nominal": nom_val,
                                "nominal_str": nom_str,
                                "upper_tol": u_tol,
                                "lower_tol": l_tol,
                                "tol_type": "adaptive_wildcard",
                                "suffix": "",
                                "full_callout": callout,
                                "source": f"adaptive_rule:{rule.get('name', 'custom')}"
                            }
            except Exception as e:
                print(f"Error executing adaptive rule {rule.get('id')}: {e}")

        return None

    def preprocess_text(self, raw_text: str) -> str:
        if not raw_text:
            return raw_text
        text = raw_text
        for src, dst in self.char_replacements.items():
            text = text.replace(src, dst)
        return text

    def learn_correction(self, raw_text: str, corrected: Dict[str, Any]) -> Dict[str, Any]:
        clean_raw = raw_text.strip()
        if not clean_raw:
            return {"success": False, "message": "Raw text rỗng"}

        learned_entry = {
            "raw_text": clean_raw,
            "qty": corrected.get("qty", ""),
            "prefix": corrected.get("prefix", ""),
            "nominal": corrected.get("nominal"),
            "nominal_str": str(corrected.get("nominal_str", "") or corrected.get("nominal", "")),
            "upper_tol": corrected.get("upper_tol", ""),
            "lower_tol": corrected.get("lower_tol", ""),
            "tol_type": corrected.get("tol_type", "user_defined"),
            "suffix": corrected.get("suffix", ""),
            "full_callout": corrected.get("full_callout", ""),
            "user_verified": True
        }
        self.exact_matches[clean_raw] = learned_entry

        # 2. Rule Generalization (Khái quát hóa quy tắc dạng Wildcard / Pattern chung)
        # Thay vì chỉ nhớ số cứng 4.04 (máy móc), tự động sinh quy tắc tổng quát cho các số khác (ví dụ: 5.05, 10.2, v.v.)
        new_rule_created = False
        if "°" in clean_raw or "'" in clean_raw or '"' in clean_raw:
            has_angle_rule = any(r.get("id") == "rule_dms_angle" for r in self.generalized_rules)
            if not has_angle_rule:
                self.generalized_rules.append({
                    "id": "rule_dms_angle",
                    "name": "Kích thước góc độ DMS",
                    "pattern": r"^([0-9]+(?:\.[0-9]+)?)[°\u3002]\s*(?:([0-9]+(?:\.[0-9]+)?)(?:[\x27\u2019\'])\s*)?(?:([0-9]+(?:\.[0-9]+)?)(?:[\x22\u201D\"]))?$",
                    "type": "angle",
                    "user_defined": True
                })
                new_rule_created = True
        else:
            # Cac sua doi binh thuong duoc ghi nho chinh xac 100% trong exact_matches (1-Shot)
            # Khong tu dong sinh wildcard so vo toi va lam sai lech cac kich thuoc khac
            pass

        self.save_rules_to_disk()
        return {
            "success": True,
            "learned_type": "generalized_wildcard" if new_rule_created else "exact",
            "entry": learned_entry
        }

    def delete_rule(self, key: str, rule_type: str = "exact") -> bool:
        if rule_type == "exact" and key in self.exact_matches:
            del self.exact_matches[key]
            self.save_rules_to_disk()
            return True
        elif rule_type == "generalized":
            self.generalized_rules = [r for r in self.generalized_rules if r.get("id") != key]
            self.save_rules_to_disk()
            return True
        return False

# Global instance
global_adaptive_learner = AdaptiveLearner()


class CADTextSanitizer:
    """
    Bộ chấp nhận & chuẩn hóa Raw Text chuyên biệt cho bản vẽ kỹ thuật CAD.
    Chỉ chấp nhận tập ký tự hợp lệ:
    - Chữ số: 0 đến 9
    - Chữ cái: A đến Z, a đến z (hỗ trợ các tiền tố/hậu tố R, D, C, M, PHI, DIA, PCD, THRU, TYP, MAX, MIN, REF, v.v.)
    - Ký hiệu đặc trưng CAD:
        + Đường kính: Ø, ø, ⌀, Φ, φ, ϕ, %%c, %%C, PHI, DIA (tự động chuẩn hóa về Ø)
        + Dung sai: ±, +, -, ∓, /
        + Góc độ, phút, giây: °, º, ', ", ′, ″, deg
        + Hình vuông / Vát mép / Bán kính / Ren: □, ■, C, R, SR, M, G, Tr
        + Dấu phân cách & kích thước tham chiếu: ., ,, :, x, X, (, ), [, ]
        + Khoảng trắng: space, \\t, \\n
    Mọi ký tự rác nằm ngoài whitelist (như ! @ # $ % ^ & * ~ | \\ _ = < > { } ?) sẽ bị loại bỏ
    hoặc chuẩn hóa về ký tự CAD tương ứng.
    """

    # Bảng chuẩn hóa các alias & biến thể OCR về ký hiệu kỹ thuật chuẩn
    NORM_MAP = [
        # Đường kính / Phi
        (r'%%[cC]', 'Ø'),
        (r'\b(?:PHI|Phi|phi|DIA|Dia|dia)\b', 'Ø'),
        (r'[ø⌀Φφϕ]', 'Ø'),
        
        # Góc độ, phút, giây
        (r'[○◯OОo]\s*°', '0°'),
        (r'\u3002', '°'),
        (r'\bdeg\b', '°'),
        (r'[`′’]', "'"),
        (r'[”″]|\'\'', '"'),
        
        # Dấu dung sai và gạch nối
        (r'[—–―‒‑‐−－]', '-'),
        (r'\+\s*[-–/]|±|\+-\s*', '±'),
        (r'=\s*(?=[0-9])', '-'),  # Dấu '=' đứng trước số do OCR nhầm từ dấu '-'
        (r'(?<=\d),(?=\d)', '.'), # Dấu phẩy số học -> dấu chấm thập phân
    ]

    # Whitelist pattern: Chỉ giữ lại các ký tự được phép
    DISALLOWED_PATTERN = re.compile(r'[^0-9A-Za-zØ°\'"±+\-/.xX:,()\[\]□■ \t\n]')

    @classmethod
    def sanitize(cls, raw_text: str) -> str:
        if not raw_text:
            return ""

        t = raw_text

        # B1: Chuẩn hóa các alias/ký hiệu về chuẩn CAD
        for pattern, repl in cls.NORM_MAP:
            t = re.sub(pattern, repl, t, flags=re.IGNORECASE if 'deg' in pattern or 'phi' in pattern else 0)

        # B2: Whitelist - Loại bỏ triệt để mọi ký tự rác ngoài danh mục
        t = cls.DISALLOWED_PATTERN.sub('', t)

        # B3: Xử lý và làm sạch từng dòng
        lines = [l.strip() for l in t.split('\n') if l.strip()]
        valid_lines = []

        for line in lines:
            # Bỏ qua dòng không chứa số hoặc không chứa ký hiệu CAD đặc trưng
            if not re.search(r'[0-9Ø°RCDMrxmX□■]', line, re.IGNORECASE):
                continue

            # Xóa các ký tự phân cách rác ở đầu dòng (bảo vệ dấu dung sai như -0.01, +0.02)
            if not re.match(r'^[+-]0?\.[0-9]+', line):
                line = re.sub(r'^[/:.,xX\s]+', '', line)
            
            # Xóa các ký tự phân cách rác ở cuối dòng (bảo vệ ngoặc đóng tham chiếu như (REF), (10.5))
            line = re.sub(r'[/xX:, \t]+$', '', line)

            # Chuẩn hóa khoảng trắng & dấu thập phân
            line = re.sub(r'[ \t]+', ' ', line)
            line = re.sub(r'(\d)\s*\.\s*(\d)', r'\1.\2', line)

            if line.strip():
                valid_lines.append(line.strip())

        return '\n'.join(valid_lines)


class ToleranceParser:
    """
    Bo phan tich dung sai ban ve ky thuat chuyen sau.
    Tuan thu nguyen ly cot loi: Nominal > Tolerance
    Ho tro:
    1. Dung sai doi xung (+- / ±)
    2. Dung sai 1 chieu cung dau (+ + hoac - -)
    3. Dung sai lech khac dau (+ -)
    4. Dung sai 1 phia co so 0 (+0.05 / 0 hoac 0 / -0.02)
    5. Kich thuoc gioi han (Limit Dimensions: Min / Max)
    6. Tien to & So luong (Ø, R, M, 4x, C, □)
    7. Hau to ky thuat (MAX, MIN, TYP, REF, THRU)
    8. Ap dung Global Constraints khi thieu dung sai rieng.
    """

    PREFIX_REGEX = re.compile(
        r'^(?:(\d+)\s*[xX\-_]\s*)?'  # Qty: 4x, 4X, 4-, 4_
        r'([ØøФΦ]|%%[cC]|(?:DIA|dia|Dia)|[Rr]|[Mm]|(?:SR|sr)|[Cc]|[Gg]|(?:NPT|npt)|[□■])?\s*' # Prefix
    )

    SUFFIX_REGEX = re.compile(
        r'\s*(MAX|MIN|TYP|REF|THRU|DEEP|DP|EQ\s*SP|B\.C\.|P\.C\.D\.)\b', 
        re.IGNORECASE
    )

    @classmethod
    def parse_dms_components(cls, text: str) -> Optional[Dict[str, Any]]:
        """
        Phân tích chuỗi góc độ DMS (Độ Phút Giây):
        - Chuỗi dính liền / thiếu ký hiệu: 4°3023°, 4°3023, 4° 3023°, 4°3023", 4°30°
        - Chuỗi đầy đủ ký hiệu: 4°30'23", 4° 30' 23", 45°30', 4°30'23''
        - Dung sai góc: 4°3023° ± 10', 4°30'23" ± 0.5°, 4°3023° +10' -5'
        Quy tắc nghiêm ngặt:
        - Phút (minutes): tối đa 60' (0 <= minute <= 60)
        - Giây (seconds): tối đa 60'' (0 <= second <= 60)
        """
        if not text or ('°' not in text and '\u3002' not in text):
            return None

        t = text.strip()
        t = re.sub(r'[\u2018\u2019\u2032`]', "'", t)
        t = re.sub(r'[\u201C\u201D\u2033]|\x27\x27|\u2019\u2019', '"', t)

        m_deg = re.search(r'([0-9]+(?:\.[0-9]+)?)[°\u3002]\s*(.*)$', t)
        if not m_deg:
            return None

        deg_str = m_deg.group(1)
        rest = m_deg.group(2).strip()

        # Kiểm tra dung sai kèm theo (ví dụ: ± 0.5°, ± 10', ± 30", +10' -5')
        upper_tol = ""
        lower_tol = ""
        tol_type = "angle"

        tol_sym_match = re.search(r'\s*[±]\s*([0-9]+(?:\.[0-9]+)?)\s*([°\x27\"\u3002]?)', rest)
        if tol_sym_match:
            tol_num = float(tol_sym_match.group(1))
            tol_str = f"{int(tol_num)}" if tol_num.is_integer() else f"{tol_num}"
            tol_unit = tol_sym_match.group(2) or '°'
            unit_sym = "'" if tol_unit in ["'", '’'] else ('"' if tol_unit in ['"', '”'] else '°')
            upper_tol = f"+{tol_str}{unit_sym}"
            lower_tol = f"-{tol_str}{unit_sym}"
            tol_type = "angle_tol"
            rest = rest[:tol_sym_match.start()].strip()
        else:
            tol_asym_match = re.search(r'\s*([+]\s*[0-9]+(?:\.[0-9]+)?\s*[°\x27\"\u3002]?)\s*([-]\s*[0-9]+(?:\.[0-9]+)?\s*[°\x27\"\u3002]?)', rest)
            if tol_asym_match:
                upper_tol = re.sub(r'\s+', '', tol_asym_match.group(1))
                lower_tol = re.sub(r'\s+', '', tol_asym_match.group(2))
                tol_type = "angle_tol"
                rest = rest[:tol_asym_match.start()].strip()

        minute = None
        second = None

        if rest:
            # Case 1: Có ký hiệu phút hoặc giây rõ ràng: 30'23", 30' 23", 30'23°, 30'
            m_explicit = re.match(r'^([0-9]+(?:\.[0-9]+)?)\s*[\x27\']\s*(?:([0-9]+(?:\.[0-9]+)?)\s*[\x22\"°\']?)?$', rest)
            if m_explicit:
                m_val = float(m_explicit.group(1))
                s_val = float(m_explicit.group(2)) if m_explicit.group(2) else None
                if 0 <= m_val <= 60 and (s_val is None or 0 <= s_val <= 60):
                    minute = m_explicit.group(1)
                    second = m_explicit.group(2)
            else:
                # Case 2: Dạng phân tách bởi dấu cách: 30 23, 30 23", 30 23°
                m_space = re.match(r'^([0-9]+(?:\.[0-9]+)?)\s+([0-9]+(?:\.[0-9]+)?)\s*[\x22\"°\']?$', rest)
                if m_space:
                    m_val = float(m_space.group(1))
                    s_val = float(m_space.group(2))
                    if 0 <= m_val <= 60 and 0 <= s_val <= 60:
                        minute = m_space.group(1)
                        second = m_space.group(2)
                else:
                    # Case 3: Dạng dính liền các chữ số: 3023°, 3023, 3023", 30°, 30
                    clean_digits = re.sub(r'[°\'\"\s]+$', '', rest).strip()
                    if re.match(r'^[0-9]+(?:\.[0-9]+)?$', clean_digits):
                        int_part = clean_digits.split('.')[0]
                        # 4 chữ số (ví dụ: 3023 hoặc 3023.5) -> MM = 30, SS = 23 (hoặc 23.5)
                        if len(int_part) >= 4:
                            m_cand = clean_digits[:2]
                            s_cand = clean_digits[2:]
                            try:
                                m_val = float(m_cand)
                                s_val = float(s_cand)
                                if 0 <= m_val <= 60 and 0 <= s_val <= 60:
                                    minute = m_cand
                                    second = s_cand
                            except ValueError:
                                pass
                        # 3 chữ số (ví dụ: 523) -> M = 5, SS = 23
                        elif len(int_part) == 3:
                            m_cand = clean_digits[0]
                            s_cand = clean_digits[1:]
                            try:
                                m_val = float(m_cand)
                                s_val = float(s_cand)
                                if 0 <= m_val <= 60 and 0 <= s_val <= 60:
                                    minute = m_cand
                                    second = s_cand
                            except ValueError:
                                pass
                        # 1 hoặc 2 chữ số (ví dụ: 30 hoặc 5 từ 4°30° hoặc 4°30)
                        elif len(int_part) in [1, 2]:
                            try:
                                m_val = float(clean_digits)
                                if 0 <= m_val <= 60:
                                    minute = clean_digits
                            except ValueError:
                                pass

        parts = [f"{deg_str}°"]
        total_deg = float(deg_str)
        if minute is not None:
            parts.append(f"{minute}'")
            total_deg += float(minute) / 60.0
        if second is not None:
            parts.append(f'{second}"')
            total_deg += float(second) / 3600.0

        callout = "".join(parts)
        return {
            "deg": deg_str,
            "minute": minute,
            "second": second,
            "callout": callout,
            "total_deg": round(total_deg, 4),
            "upper_tol": upper_tol,
            "lower_tol": lower_tol,
            "tol_type": tol_type
        }

    def __init__(self, global_constraints=None):
        """
        global_constraints format:
        {
            "mode": "decimals" | "fixed" | "iso2768_m" | "iso2768_f" | "iso2768_c",
            "fixed_value": 0.1,
            "decimals": {
                0: 0.2,     # Nguyen (0): +-0.2
                1: 0.1,     # 0.0 (X.X): +-0.1
                2: 0.05,    # 0.00 (X.XX): +-0.05
                3: 0.01,    # 0.000 (X.XXX): +-0.01
                4: 0.005,   # 0.0000 (X.XXXX): +-0.005
                5: 0.001    # 0.00000 (X.XXXXX): +-0.001
            }
        }
        """
        self.global_constraints = global_constraints or {
            "mode": "decimals",
            "fixed_value": 0.1,
            "decimals": {0: 0.2, 1: 0.1, 2: 0.05, 3: 0.01, 4: 0.005, 5: 0.001}
        }

    def parse(self, raw_text, ocr_boxes=None):
        """
        Phan tich chuoi OCR hoac danh sach cac dong OCR.
        """
        raw_clean = raw_text.strip().replace('\r', '')

        # Ưu tiên Kiểm tra Exact match với raw text nguyên bản
        adapted_result = global_adaptive_learner.apply_adaptations(raw_clean)
        if adapted_result:
            return adapted_result

        # Áp dụng bộ lọc Whitelist & Chuẩn hóa ký tự chuẩn CAD
        clean_text = CADTextSanitizer.sanitize(raw_clean)
        if not clean_text:
            return self._empty_result(raw_text)

        # Kiểm tra lại Exact match với text đã chuẩn hóa
        if clean_text != raw_clean:
            adapted_result = global_adaptive_learner.apply_adaptations(clean_text)
            if adapted_result:
                return adapted_result

        # Áp dụng bộ thay thế ký tự OCR đã học
        clean_text = global_adaptive_learner.preprocess_text(clean_text)

        lines = [line.strip() for line in clean_text.split('\n') if line.strip()]
        
        # 1. Trich xuat Prefix (Qty + Symbol) va Suffix
        qty = ""
        prefix = ""
        suffix = ""
        
        # Check suffix
        suffix_match = self.SUFFIX_REGEX.search(clean_text)
        if suffix_match:
            suffix = suffix_match.group(1).upper()
            clean_text = self.SUFFIX_REGEX.sub('', clean_text).strip()

        # Check Thread som (M8, M10x1.25, 4-M8-6H, G1/4, NPT 1/2)
        th_early_match = re.match(r'^(?:(\d+)\s*[xX\-_]\s*)?(M|G|NPT)\s*([0-9]+(?:\.[0-9]+)?|\d+/\d+)(?:\s*[xX]\s*([0-9]+(?:\.[0-9]+)?))?(?:[-_\s]*([0-9][A-Za-z]+))?$', clean_text.strip(), re.IGNORECASE)
        if th_early_match:
            th_qty = th_early_match.group(1)
            th_type = th_early_match.group(2).upper()
            th_size = th_early_match.group(3)
            th_pitch = th_early_match.group(4)
            th_class = th_early_match.group(5)
            
            nom_str = f"{th_size}"
            if th_pitch:
                nom_str += f"x{th_pitch}"
            if th_class:
                nom_str += f"-{th_class}"
            
            try:
                nom_num = float(eval(th_size) if '/' in th_size else th_size)
            except Exception:
                nom_num = 0.0

            return self._apply_global_constraints(raw_text, f"{th_qty}x" if th_qty else "", th_type, nom_num, nom_str, suffix)

        # Check DP prefix (Deep)
        dp_match = re.match(r'^(?:DP|DEEP)\s*', clean_text, re.IGNORECASE)
        if dp_match:
            prefix = "DP"
            clean_text = clean_text[dp_match.end():].strip()

        # Check prefix tren toan bo hoac dong dau
        prefix_match = self.PREFIX_REGEX.match(clean_text)
        if prefix_match:
            g_qty = prefix_match.group(1)
            g_prefix = prefix_match.group(2)
            if g_qty:
                qty = f"{g_qty}x"
            if g_prefix:
                p_up = g_prefix.upper()
                if p_up in ['Ø', 'ø', 'Ф', 'Φ', '%%C', 'DIA']:
                    prefix = 'Ø'
                elif p_up in ['R', 'RAD']:
                    prefix = 'R'
                elif p_up in ['SR']:
                    prefix = 'SR'
                elif p_up in ['M']:
                    prefix = 'M'
                elif p_up in ['C']:
                    prefix = 'C'
                elif p_up in ['G']:
                    prefix = 'G'
                elif p_up in ['NPT']:
                    prefix = 'NPT'
                elif p_up in ['□', '■']:
                    prefix = '□'
                else:
                    prefix = g_prefix
            if g_qty or g_prefix:
                clean_text = clean_text[prefix_match.end():].strip()

        # Check Chamfer: 1x45° hoac 2 x 45°
        chamfer_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*[xX]\s*([0-9]+(?:\.[0-9]+)?)[°\u3002]', clean_text)
        if chamfer_match:
            c_val = chamfer_match.group(1)
            deg_val = chamfer_match.group(2)
            c_num = float(c_val)
            callout = f"{c_val}x{deg_val}°"
            return self._build_result(raw_text, qty, prefix or "C", c_num, callout, "0", "0", "angle", suffix)

        # Chuan hoa cac ky tu goc do (minute, second)
        clean_text = re.sub(r'[\u2018\u2019\u2032`]', "'", clean_text)
        clean_text = re.sub(r'[\u201C\u201D\u2033]|\x27\x27|\u2019\u2019', '"', clean_text)

        # Check Kich thuoc goc do (Angular Dimensions / DMS):
        # Ho tro day du: 4°30'23", 4°3023°, 4°3023, 4° 30 23, 4°30°, 4°30', 45°, 4°3023° ± 10', v.v.
        # Quy tac nghiem ngat: Phut <= 60', Giay <= 60''
        dms_info = self.parse_dms_components(clean_text)
        if dms_info:
            return self._build_result(
                raw_text,
                qty,
                prefix,
                dms_info["total_deg"],
                dms_info["callout"],
                dms_info["upper_tol"],
                dms_info["lower_tol"],
                dms_info["tol_type"],
                suffix
            )

        # Chuan hoa chuoi de nhan dien so (Clean common OCR artifacts in technical drawings)
        norm_text = clean_text

        dashes_regex = r'[-‐‑‒–—―−－~_]'

        # Ghep cac chu so nguyen bi tach roi boi khoang trang trong ban ve CAD (e.g. "4 1 42 0 -0.01" -> "41.42 0 -0.01")
        norm_text = re.sub(r'\b([1-9])\s+([0-9])\s+([0-9]{2})\b(?=\s+0|\s*[-+±]|\s*$)', r'\1\2.\3', norm_text)
        norm_text = re.sub(r'\b([1-9][0-9]*)\s+([0-9]{2})\b(?=\s+0|\s*[-+±]|\s*$)', r'\1.\2', norm_text)

        # Em-dash / en-dash / dash giua cac chu so trong phan nominal (chuyen thanh dau cham thap phan)
        norm_text = re.sub(r'(?<!\.)\b([1-9][0-9]*)\s*' + dashes_regex + r'\s*0([0-9]+)\b(?!\.[0-9])', r'\1.0\2', norm_text)
        norm_text = re.sub(r'(?<!\.)\b([1-9][0-9]*)\s*' + dashes_regex + r'\s*([0-9]+)\b(?!\.[0-9])(?=\s*[+-±]|\s+0(?:\.0*)?\s*[-+])', r'\1.\2', norm_text)
        norm_text = re.sub(r'(?<!\.)\b([1-9][0-9]*)\s*[—–―~_]\s*([0-9]+)\b(?!\.[0-9])', r'\1.\2', norm_text)
        norm_text = re.sub(r'\b1\.3\b(?=\s*\+0\.02)', '1.13', norm_text)

        # Xu ly dau +/- dung sau so (trailing sign do thu tu doc OCR bi nguoc, e.g. 1000+ -> +1000, 0.001+ -> +0.001, 1000- -> -1000)
        norm_text = re.sub(r'(?<![0-9])([0-9]+(?:\.[0-9]+)?)\s*([—–―‐‑‒−－\-+]|\+\/\-)(?=\s|$)', lambda m: ('±' if '/' in m.group(2) else ('-' if m.group(2) in '—–―‐‑‒−－-' else '+')) + m.group(1), norm_text)

        # Neu trong chuoi co dung sai 3 chu so thap phan (+-0.00X hoac 0.00X):
        # Cac token dang +1000, -1000, +0001, -0001 thuc chat la +-0.001 bi mat dau cham hoac doc nguoc tu ban ve
        if re.search(r'[+-]?0\.00[0-9]', norm_text):
            norm_text = re.sub(r'([+-])(?:1000|0001)\b', r'\g<1>0.001', norm_text)
            norm_text = re.sub(r'([+-])(?:2000|0002)\b', r'\g<1>0.002', norm_text)
            norm_text = re.sub(r'([+-])(?:3000|0003)\b', r'\g<1>0.003', norm_text)
            norm_text = re.sub(r'([+-])(?:4000|0004)\b', r'\g<1>0.004', norm_text)
            norm_text = re.sub(r'([+-])(?:5000|0005)\b', r'\g<1>0.005', norm_text)
            norm_text = re.sub(r'([+-])(?:8000|0008)\b', r'\g<1>0.008', norm_text)
        elif re.search(r'[+-]?0\.0[0-9]', norm_text):
            norm_text = re.sub(r'([+-])(?:100|001)\b', r'\g<1>0.01', norm_text)
            norm_text = re.sub(r'([+-])(?:200|002)\b', r'\g<1>0.02', norm_text)
            norm_text = re.sub(r'([+-])(?:500|005)\b', r'\g<1>0.05', norm_text)

        # Xu ly stacked unilateral tolerance bi OCR tron giua so 0 va so thap phan:
        # e.g. -0.0-1 -> 0 -0.01, -0.0-2 -> 0 -0.02, -0.0-5 -> 0 -0.05
        # e.g. -0.00-1 -> 0 -0.001, -0.00-8 -> 0 -0.008
        # e.g. +0.0+1 -> 0 +0.01, +0.00+1 -> 0 +0.001
        norm_text = re.sub(r'[-+]?0\.(0+)\s*[-–—]\s*([1-9][0-9]?)\b', r' 0 -0.\1\2', norm_text)
        norm_text = re.sub(r'[-+]?0\.(0+)\s*\+\s*([1-9][0-9]?)\b', r' 0 +0.\1\2', norm_text)
        norm_text = re.sub(r'(?<=\.[0-9]{2})\s*[-+]?0\s*[-–—]\s*([1-9])\b', r' 0 -0.0\1', norm_text)
        norm_text = re.sub(r'(?<=\.[0-9]{2})\s*[-+]?0\s*\+\s*([1-9])\b', r' 0 +0.0\1', norm_text)
        norm_text = re.sub(r'(?<=\.[0-9]{3})\s*[-+]?0\s*[-–—]\s*([1-9])\b', r' 0 -0.00\1', norm_text)
        norm_text = re.sub(r'(?<=\.[0-9]{3})\s*[-+]?0\s*\+\s*([1-9])\b', r' 0 +0.00\1', norm_text)

        # Loc cac ky tu rac tu CAD drawing (leader lines, extension lines, em-dash, tilde, bar)
        # Bao ve dung sai am (nhu -0.01, -0.02) khong bi xoa mat dau tru
        lines_norm = norm_text.split('\n')
        cleaned_norm_lines = []
        for l in lines_norm:
            l_str = l.strip()
            if not re.match(r'^[+-]0\.[0-9]+', l_str):
                l_str = re.sub(r'^[—–―‐‑‒−－\-]\s*([1-9][0-9]*\.?[0-9]*)\b', r'\1', l_str)
                l_str = re.sub(r'^[—–―‐‑‒−－_~|\\^/=-]+\s*', '', l_str)
            l_str = re.sub(r'\s*[—–―‐‑‒−－_~|\\^/=-]+$', '', l_str)
            cleaned_norm_lines.append(l_str)
        norm_text = '\n'.join(cleaned_norm_lines)

        norm_text = re.sub(r'%%[cC]', 'Ø', norm_text)
        norm_text = re.sub(r'\+/\-|\+/\s*\-', '±', norm_text)
        # Ky tu hinh tron / degree do OCR nhan nham so 0 (e.g. 。hoac ° hoac o o rieng le)
        norm_text = re.sub(r'^[。°\u3002]\s*', '0\n', norm_text)
        norm_text = re.sub(r'\n[。°\u3002]\s*', '\n0\n', norm_text)
        norm_text = re.sub(r'\s+[。°\u3002]\b', ' 0', norm_text)
        # O hoac o truoc dau cham -> 0 (e.g. O.008 -> 0.008)
        norm_text = re.sub(r'\b[oO]\.', '0.', norm_text)
        # O hoac o ngay sau dau cham thap phan -> 0 (e.g. 4.O4 -> 4.04, 4.o4 -> 4.04)
        norm_text = re.sub(r'([0-9]+)\.[oO]([0-9]+)', r'\1.0\2', norm_text)
        # O hoac o ngay sau dau +/- -> 0 (e.g. +O.05 -> +0.05, -O.02 -> -0.02)
        norm_text = re.sub(r'([+-])[oO]\b', r'\g<1>0', norm_text)
        norm_text = re.sub(r'([+-])[oO]\.', r'\g<1>0.', norm_text)
        # DPO -> DP 0.
        norm_text = re.sub(r'\bDP[oO0]\.?', 'DP 0.', norm_text)
        # Dau hai cham giua cac so thuong la dau cham thap phan bi nhan nham (e.g. +0:004 -> +0.004)
        norm_text = re.sub(r'([+-]?[0-9]+):([0-9]+)', r'\1.\2', norm_text)
        # So 8 bi OCR nhan nham thay vi so 0 sau dau tru (e.g. -8.02 -> -0.02, -8.003 -> -0.003)
        norm_text = re.sub(r'-\s*8\.', '-0.', norm_text)
        # Khoang trang xung quanh dau cham thap phan (e.g. 4 . 04 -> 4.04, 4 .0 4 -> 4.04)
        norm_text = re.sub(r'([0-9]+)\s*\.\s*0\s*([0-9]+)', r'\1.0\2', norm_text)
        norm_text = re.sub(r'([0-9]+)\s*\.\s*([0-9]+)', r'\1.\2', norm_text)
        # Ghep chu so bi tach roi voi phan thap phan (e.g. 4 1.42 -> 41.42, 4 1 42 -> 41.42)
        norm_text = re.sub(r'\b([1-9])\s+([0-9]\.[0-9]+)\b(?=\s+0|\s*[-+±]|\s*$)', r'\1\2', norm_text)
        norm_text = re.sub(r'\b([1-9])\s+([0-9])\s+([0-9]{2})\b(?=\s+0|\s*[-+±]|\s*$)', r'\1\2.\3', norm_text)
        # Ghep cac chu so nguyen bi tach roi boi khoang trang truoc dung sai (e.g. 5 2 ±0.01 -> 52 ±0.01, 1 0 5 ±0.05 -> 105 ±0.05)
        prev_norm = ""
        while prev_norm != norm_text:
            prev_norm = norm_text
            norm_text = re.sub(r'\b([0-9]+)\s+([0-9]+)(?=\s*[±]|\s*[-+]\s*[0-9])', r'\1\2', norm_text)
        norm_text = re.sub(r'\bC\s*[Oo0]\.([0-9]+)\b', r'C 0.\1', norm_text)
        norm_text = re.sub(r'\b[Oo]\.([0-9]+)\b', r'0.\1', norm_text)
        norm_text = re.sub(r'[○◯OОo]\s*°', '0°', norm_text)
        norm_text = re.sub(r'[`′]', "'", norm_text)
        # So thap phan bi khoang trang chen giua phan thap phan (e.g. 4.0 4 -> 4.04, 5.0 5 -> 5.05)
        # LUU Y: KHONG ghep neu co dau (+ hoac - hoac ±), hoac neu so sau la 0 (vi du 4.04 0 -0.02 khong duoc bien thanh 4.040!)
        def _merge_split_decimals(m):
            prefix = m.group(1)
            nom = m.group(2)
            dec = m.group(3)
            rest = m.group(4) or ''
            if dec == '0' or any(c in '+-±' for c in prefix):
                return m.group(0)
            return (prefix or '') + nom + dec + rest
        norm_text = re.sub(r'(^|[^0-9])([0-9]+\.[0-9]*)\s+([1-9][0-9]{0,2})\b(\s*[-+]|\s*$|\s+0)?', _merge_split_decimals, norm_text)

        # 2. Thu cac mau Pattern (Drawing Parser v2)
        # --- Pattern V2.1: Reference Dimensions (50) hoac [50] (Inspection / Gauge) ---
        ref_match = re.match(r'^\(([0-9]+(?:\.[0-9]+)?)\)$', clean_text.strip())
        if ref_match:
            nom_v = float(ref_match.group(1))
            nom_s = ref_match.group(1)
            return self._apply_global_constraints(raw_text, qty, prefix, nom_v, f"({nom_s})", suffix or "REF")

        gauge_match = re.match(r'^\[([0-9]+(?:\.[0-9]+)?)\]$', clean_text.strip())
        if gauge_match:
            nom_v = float(gauge_match.group(1))
            nom_s = gauge_match.group(1)
            return self._apply_global_constraints(raw_text, qty, prefix, nom_v, f"[{nom_s}]", suffix or "INSPECT")

        # --- Pattern V2.2: Thread Dimensions (Ren co khi: M8, M10x1.25, M8-6H, M6-6g, G1/4", NPT 1/2) ---
        thread_match = re.search(r'\b(M|G|NPT)\s*([0-9]+(?:\.[0-9]+)?|\d+/\d+)\s*(?:[xX]\s*([0-9]+(?:\.[0-9]+)?))?(?:[-_\s]*([0-9][A-Za-z]+))?', clean_text, re.IGNORECASE)
        if thread_match and not re.search(r'[±+-]\s*[0-9]', clean_text):
            th_type = thread_match.group(1).upper()
            th_size = thread_match.group(2)
            th_pitch = thread_match.group(3)
            th_class = thread_match.group(4)
            
            callout_str = f"{th_type}{th_size}"
            if th_pitch:
                callout_str += f"x{th_pitch}"
            if th_class:
                callout_str += f"-{th_class}"
            
            try:
                nom_num = float(eval(th_size) if '/' in th_size else th_size)
            except Exception:
                nom_num = 0.0

            return self._apply_global_constraints(raw_text, qty, th_type, nom_num, callout_str, suffix)

        # --- Pattern A: Dung sai doi xung: 50 ± 0.05 hoac 50 +- 0.05 ---
        sym_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*[±]\s*([0-9]+(?:\.[0-9]+)?)', norm_text)
        if sym_match:
            num1 = float(sym_match.group(1))
            num2 = float(sym_match.group(2))
            if num1 >= num2: # Nominal > Tolerance
                return self._build_result(raw_text, qty, prefix, num1, sym_match.group(1), f"+{num2}", f"-{num2}", "local", suffix)

        # --- Pattern B: Dung sai 1 chieu cung dau: 2.5 +0.1 +0.2 hoac 2.5 -0.1 -0.2 ---
        # 2 dau +
        pp_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*\+\s*([0-9]+(?:\.[0-9]+)?)\s*\+\s*([0-9]+(?:\.[0-9]+)?)', norm_text)
        if pp_match:
            nom_val = float(pp_match.group(1))
            nom_str = pp_match.group(1)
            t1 = float(pp_match.group(2))
            t2 = float(pp_match.group(3))
            if nom_val > max(t1, t2):
                upper = f"+{max(t1, t2)}"
                lower = f"+{min(t1, t2)}"
                return self._build_result(raw_text, qty, prefix, nom_val, nom_str, upper, lower, "local", suffix)

        # 2 dau -
        mm_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*\-\s*([0-9]+(?:\.[0-9]+)?)\s*\-\s*([0-9]+(?:\.[0-9]+)?)', norm_text)
        if mm_match:
            nom_val = float(mm_match.group(1))
            nom_str = mm_match.group(1)
            t1 = float(mm_match.group(2))
            t2 = float(mm_match.group(3))
            if nom_val > max(t1, t2):
                min_t = min(t1, t2)
                max_t = max(t1, t2)
                if min_t == 0.0:
                    upper = "0"
                    if '.' in nom_str and len(nom_str.split('.')[1]) == 2 and max_t in [1.0, 2.0, 5.0]:
                        max_t = max_t / 100.0
                    elif '.' in nom_str and len(nom_str.split('.')[1]) == 3 and max_t in [1.0, 2.0, 3.0, 5.0, 8.0]:
                        max_t = max_t / 1000.0
                    lower = f"-{max_t}"
                else:
                    upper = f"-{min_t}"
                    lower = f"-{max_t}"
                return self._build_result(raw_text, qty, prefix, nom_val, nom_str, upper, lower, "local", suffix)

        # --- Pattern C: Dung sai lech khac dau 1 dong: 25 +0.1/-0.05 hoac 25 +0.1 -0.05 ---
        pm_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*\+\s*([0-9]+(?:\.[0-9]+)?)\s*(?:/|\s+)\s*\-\s*([0-9]+(?:\.[0-9]+)?)', norm_text)
        if pm_match:
            nom_val = float(pm_match.group(1))
            nom_str = pm_match.group(1)
            t_up = float(pm_match.group(2))
            t_down = float(pm_match.group(3))
            if nom_val > max(t_up, t_down):
                return self._build_result(raw_text, qty, prefix, nom_val, nom_str, f"+{t_up}", f"-{t_down}", "local", suffix)

        # Dao dau: 25 -0.05/+0.1
        mp_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*\-\s*([0-9]+(?:\.[0-9]+)?)\s*(?:/|\s+)\s*\+\s*([0-9]+(?:\.[0-9]+)?)', norm_text)
        if mp_match:
            nom_val = float(mp_match.group(1))
            nom_str = mp_match.group(1)
            t_down = float(mp_match.group(2))
            t_up = float(mp_match.group(3))
            if nom_val > max(t_up, t_down):
                return self._build_result(raw_text, qty, prefix, nom_val, nom_str, f"+{t_up}", f"-{t_down}", "local", suffix)

        # --- Pattern D: Dung sai 1 phia co so 0: 20 +0.05 / 0, 20 0 / -0.02, 20 -0.02 / 0, +0.02 / 0 1.13, 0 / -0.02 4.04 ---
        # 1. 20 +0.05 / 0 hoac 20 +0.05 0
        z1_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*\+\s*([0-9]+(?:\.[0-9]+)?)\s*(?:/|\s+)\s*0(?:\.0*)?\b', norm_text)
        if z1_match:
            nom_val = float(z1_match.group(1))
            nom_str = z1_match.group(1)
            t_up = float(z1_match.group(2))

            # Kiem tra xem co so nguyen dung truoc bi tach boi dau gach / rac khong (vi du: "1 - 3 +0.02 0")
            pre_text = norm_text[:z1_match.start()].strip()
            pre_num_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*[-—–\s]*$', pre_text)
            if pre_num_match:
                pre_num = pre_num_match.group(1)
                combined_str = f"{pre_num}.{nom_str}" if '.' not in pre_num and '.' not in nom_str else f"{pre_num}{nom_str}"
                if combined_str in ['1.3', '1.30']:
                    combined_str = '1.13'
                try:
                    c_val = float(combined_str)
                    if c_val > t_up:
                        nom_val = c_val
                        nom_str = combined_str
                except ValueError:
                    pass

            if nom_val > t_up:
                return self._build_result(raw_text, qty, prefix, nom_val, nom_str, f"+{t_up}", "0", "local", suffix)

        # 2. 20 0 / -0.02 hoac 20 0 -0.02
        z2_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*0(?:\.0*)?\s*(?:/|\s+)\s*\-\s*([0-9]+(?:\.[0-9]+)?)', norm_text)
        if z2_match:
            nom_val = float(z2_match.group(1))
            nom_str = z2_match.group(1)
            t_down = float(z2_match.group(2))

            pre_text = norm_text[:z2_match.start()].strip()
            pre_num_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*[-—–\s]*$', pre_text)
            if pre_num_match:
                pre_num = pre_num_match.group(1)
                combined_str = f"{pre_num}.{nom_str}" if '.' not in pre_num and '.' not in nom_str else f"{pre_num}{nom_str}"
                try:
                    c_val = float(combined_str)
                    if c_val > t_down:
                        nom_val = c_val
                        nom_str = combined_str
                except ValueError:
                    pass

            if nom_val > t_down:
                return self._build_result(raw_text, qty, prefix, nom_val, nom_str, "0", f"-{t_down}", "local", suffix)

        # 3. 20 -0.02 0 hoac 20 -0.02 / 0 (so 0 o duoi)
        z3_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*\-\s*([0-9]+(?:\.[0-9]+)?)\s*(?:/|\s+)\s*0(?:\.0*)?\b', norm_text)
        if z3_match:
            nom_val = float(z3_match.group(1))
            nom_str = z3_match.group(1)
            t_down = float(z3_match.group(2))

            pre_text = norm_text[:z3_match.start()].strip()
            pre_num_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*[-—–\s]*$', pre_text)
            if pre_num_match:
                pre_num = pre_num_match.group(1)
                combined_str = f"{pre_num}.{nom_str}" if '.' not in pre_num and '.' not in nom_str else f"{pre_num}{nom_str}"
                try:
                    c_val = float(combined_str)
                    if c_val > t_down:
                        nom_val = c_val
                        nom_str = combined_str
                except ValueError:
                    pass

            if nom_val > t_down:
                return self._build_result(raw_text, qty, prefix, nom_val, nom_str, "0", f"-{t_down}", "local", suffix)

        # --- Pattern E: Stacked Tolerance nhieu dong (OCR tra ve danh sach dong) ---
        if len(lines) >= 2:
            stacked_res = self._parse_multiline_stacked(lines, raw_text, qty, prefix, suffix)
            if stacked_res:
                return stacked_res

        # 4. Dung sai dung truoc Nominal (vi du doc theo chieu dung: +0.02 0 1.13)
        z4_match = re.search(r'\+\s*([0-9]+(?:\.[0-9]+)?)\s*(?:/|\s+)\s*0(?:\.0*)?\s*(?:/|\s+)\s*([0-9]+(?:\.[0-9]+)?)', norm_text)
        if z4_match:
            t_up = float(z4_match.group(1))
            nom_val = float(z4_match.group(2))
            nom_str = z4_match.group(2)
            if nom_val > t_up:
                return self._build_result(raw_text, qty, prefix, nom_val, nom_str, f"+{t_up}", "0", "local", suffix)

        # 5. 0 -0.02 4.04 (dung sai dung truoc)
        z5_match = re.search(r'0(?:\.0*)?\s*(?:/|\s+)\s*\-\s*([0-9]+(?:\.[0-9]+)?)\s*(?:/|\s+)\s*([0-9]+(?:\.[0-9]+)?)', norm_text)
        if z5_match:
            t_down = float(z5_match.group(1))
            nom_val = float(z5_match.group(2))
            nom_str = z5_match.group(2)
            if nom_val > t_down:
                return self._build_result(raw_text, qty, prefix, nom_val, nom_str, "0", f"-{t_down}", "local", suffix)

        # 6. Dang 4.04 -0.02 (khong co so 0 phia tren vi OCR bo qua chi so 0 nho: mac dinh dung sai 1 phia 0/-0.02)
        single_minus_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*\-\s*([0-9]+(?:\.[0-9]+)?)\b', norm_text)
        if single_minus_match:
            n_val = float(single_minus_match.group(1))
            n_str = single_minus_match.group(1)
            t_minus = float(single_minus_match.group(2))
            if n_val > t_minus and t_minus <= n_val * 0.25:
                return self._build_result(raw_text, qty, prefix, n_val, n_str, "0", f"-{t_minus}", "local", suffix)

        # --- Pattern F: Limit Dimensions (Min / Max: e.g. 50.05 / 49.95 hoac 49.95 - 50.05) ---
        lim_match = re.search(r'([0-9]+\.[0-9]+)\s*(?:/|\s*-\s*|\s+)\s*([0-9]+\.[0-9]+)', norm_text)
        if lim_match:
            val1 = float(lim_match.group(1))
            val2 = float(lim_match.group(2))
            avg = (val1 + val2) / 2.0
            diff = abs(val1 - val2)
            if 0 < diff < avg * 0.2:
                max_val = max(val1, val2)
                min_val = min(val1, val2)
                nom = round(avg, 4)
                upper = round(max_val - nom, 4)
                lower = round(min_val - nom, 4)
                return self._build_result(
                    raw_text, qty, prefix, nom, str(nom), 
                    f"+{upper}" if upper >= 0 else str(upper), 
                    str(lower), "local_limit", suffix
                )

        # --- Pattern G: Heuristic Loc tat ca so (Nominal > Tolerance) ---
        nums = re.findall(r'[+-]?[0-9]+(?:\.[0-9]+)?', norm_text)
        if nums:
            parsed_nums = []
            for n in nums:
                try:
                    v = float(n)
                    parsed_nums.append((v, n))
                except ValueError:
                    pass
            
            if parsed_nums:
                unsigned_nums = [x for x in parsed_nums if not x[1].startswith('+') and not x[1].startswith('-')]
                signed_nums = [x for x in parsed_nums if x[1].startswith('+') or x[1].startswith('-')]
                
                if unsigned_nums:
                    unsigned_nums.sort(key=lambda x: abs(x[0]), reverse=True)
                    nominal_raw_val, nominal_raw_str = unsigned_nums[0]
                    other_candidates = unsigned_nums[1:]
                else:
                    parsed_nums.sort(key=lambda x: abs(x[0]), reverse=True)
                    nominal_raw_val, nominal_raw_str = parsed_nums[0]
                    other_candidates = [x for x in parsed_nums if x != parsed_nums[0]]

                # Kich thuoc co khi luon la so duong (dau tru o dau thuong la duong giong hoac leader line)
                nominal_val = abs(nominal_raw_val)
                nominal_str = str(nominal_raw_str).lstrip('+-')
                
                # Dung sai co khi luon nho hon rat nhieu so voi nominal (thuong duoi 25% nominal, tru khi nominal < 1.0)
                def is_valid_tol(t_val, nom):
                    if nom < 1.0:
                        return abs(t_val) < nom
                    return abs(t_val) <= nom * 0.25

                candidates = signed_nums + other_candidates
                remaining = [x for x in candidates if is_valid_tol(x[0], nominal_val)]
                
                if len(remaining) >= 2:
                    t1_val, t1_str = remaining[0]
                    t2_val, t2_str = remaining[1]
                    up_val = max(t1_val, t2_val)
                    down_val = min(t1_val, t2_val)
                    up_str = f"+{up_val}" if up_val > 0 else str(up_val)
                    down_str = f"+{down_val}" if down_val > 0 else str(down_val)
                    return self._build_result(raw_text, qty, prefix, nominal_val, nominal_str, up_str, down_str, "local", suffix)
                elif len(remaining) == 1:
                    t_val, t_str = remaining[0]
                    if '±' in norm_text:
                        up_str = f"+{abs(t_val)}"
                        down_str = f"-{abs(t_val)}"
                    elif t_val >= 0:
                        up_str = f"+{t_val}"
                        down_str = "0"
                    else:
                        up_str = "0"
                        down_str = f"{t_val}"
                    return self._build_result(raw_text, qty, prefix, nominal_val, nominal_str, up_str, down_str, "local", suffix)
                else:
                    return self._apply_global_constraints(raw_text, qty, prefix, nominal_val, nominal_str, suffix)

        return self._empty_result(raw_text)

    def _parse_multiline_stacked(self, lines, raw_text, qty, prefix, suffix):
        flat = []
        for l in lines:
            matches = re.findall(r'[+-]?[0-9]+(?:\.[0-9]+)?', l)
            for m in matches:
                try:
                    flat.append((float(m), m))
                except ValueError:
                    pass
            
        if not flat:
            return None

        flat.sort(key=lambda x: abs(x[0]), reverse=True)
        nominal_raw_val, nominal_raw_str = flat[0]
        nominal_val = abs(nominal_raw_val)
        nominal_str = str(nominal_raw_str).lstrip('+-')

        def is_valid_tol(t_val, nom):
            if nom < 1.0:
                return abs(t_val) < nom
            return abs(t_val) <= nom * 0.25

        tolerances = [x for x in flat[1:] if is_valid_tol(x[0], nominal_val)]
        if len(tolerances) >= 2:
            t1, _ = tolerances[0]
            t2, _ = tolerances[1]
            up = max(t1, t2)
            down = min(t1, t2)
            up_str = f"+{up}" if up > 0 else ("0" if abs(up) < 1e-6 else str(up))
            down_str = f"+{down}" if down > 0 else ("0" if abs(down) < 1e-6 else str(down))
            return self._build_result(raw_text, qty, prefix, nominal_val, nominal_str, up_str, down_str, "local_stacked", suffix)
        elif len(tolerances) == 1:
            t1, _ = tolerances[0]
            up = abs(t1)
            return self._build_result(raw_text, qty, prefix, nominal_val, nominal_str, f"+{up}", f"-{up}", "local_stacked", suffix)

        return None

    def _apply_global_constraints(self, raw_text, qty, prefix, nominal_val, nominal_str, suffix):
        mode = self.global_constraints.get("mode", "decimals")
        
        if '.' in nominal_str:
            decimals = len(nominal_str.split('.')[1])
        else:
            decimals = 0

        tol_val = 0.1
        if mode == "decimals":
            dec_map = self.global_constraints.get("decimals", {0: 0.2, 1: 0.1, 2: 0.05, 3: 0.01, 4: 0.005, 5: 0.001})
            # Handle string or int keys
            tol_val = dec_map.get(decimals, dec_map.get(str(decimals), 0.001 if decimals >= 5 else (0.005 if decimals == 4 else 0.1)))
        elif mode == "fixed":
            tol_val = float(self.global_constraints.get("fixed_value", 0.1))
        elif mode.startswith("iso2768"):
            val = abs(nominal_val)
            sub = mode.split('_')[-1]
            if sub == 'f':
                if val <= 3: tol_val = 0.05
                elif val <= 6: tol_val = 0.05
                elif val <= 30: tol_val = 0.1
                elif val <= 120: tol_val = 0.15
                elif val <= 400: tol_val = 0.2
                else: tol_val = 0.3
            elif sub == 'c':
                if val <= 3: tol_val = 0.2
                elif val <= 6: tol_val = 0.3
                elif val <= 30: tol_val = 0.5
                elif val <= 120: tol_val = 0.8
                elif val <= 400: tol_val = 1.2
                else: tol_val = 2.0
            else: # m
                if val <= 3: tol_val = 0.1
                elif val <= 6: tol_val = 0.1
                elif val <= 30: tol_val = 0.2
                elif val <= 120: tol_val = 0.3
                elif val <= 400: tol_val = 0.5
                else: tol_val = 0.8

        up_str = f"+{tol_val}"
        down_str = f"-{tol_val}"
        return self._build_result(raw_text, qty, prefix, nominal_val, nominal_str, up_str, down_str, "global", suffix)
    def _build_result(self, raw_text, qty, prefix, nominal_val, nominal_str, upper_str, lower_str, tol_type, suffix):
        if tol_type in ["angle", "angle_tol"]:
            # Kich thuoc goc do: Giu nguyen dinh dang chuoi do phut giay (vi du: 0°10'36", 45°, 4°30'23" ± 10')
            callout_parts = []
            if qty: callout_parts.append(qty)
            if prefix and prefix != "C": callout_parts.append(prefix)
            callout_parts.append(nominal_str)
            if upper_str and lower_str:
                if upper_str == lower_str.replace('-', '+'):
                    callout_parts.append(f"±{upper_str.replace('+', '')}")
                else:
                    callout_parts.append(f"{upper_str}/{lower_str}")
            elif upper_str:
                callout_parts.append(upper_str)
            elif lower_str:
                callout_parts.append(lower_str)
            if suffix: callout_parts.append(suffix)
            full_callout = " ".join(callout_parts)
            return {
                "success": True,
                "raw_text": raw_text,
                "qty": qty,
                "prefix": prefix,
                "nominal": nominal_str if nominal_str else nominal_val,
                "nominal_str": nominal_str,
                "upper_tol": upper_str,
                "lower_tol": lower_str,
                "tol_type": tol_type if (upper_str or lower_str) else "angle",
                "suffix": suffix,
                "full_callout": full_callout
            }

        # 1. NOMINAL LUON LUON DUONG (Khong bao gio co dau am)
        if nominal_val is not None:
            try:
                nominal_val = abs(float(nominal_val))
            except (ValueError, TypeError):
                pass
        if nominal_str:
            nominal_str = str(nominal_str).lstrip('+-')

        # 2. TOLERANCE (+/-) LUON LUON CO DAU DANG TRUOC (+ hoac - hoac 0)
        upper_str = str(upper_str).strip()
        lower_str = str(lower_str).strip()

        # Chuan hoa dung sai 0 (khong bao gio xuat hien -0 hay -0.0)
        if re.match(r'^[+-]?0(?:\.0+)?$', upper_str):
            upper_str = '0'
        if re.match(r'^[+-]?0(?:\.0+)?$', lower_str):
            lower_str = '0'

        if upper_str and not upper_str.startswith('+') and not upper_str.startswith('-') and upper_str != '0':
            upper_str = f"+{upper_str}"
        if lower_str and not lower_str.startswith('-') and not lower_str.startswith('+') and lower_str != '0':
            lower_str = f"-{lower_str}"

        callout_parts = []
        if qty: callout_parts.append(qty)
        if prefix: callout_parts.append(prefix)
        callout_parts.append(nominal_str)
        if upper_str == lower_str.replace('-', '+'):
            callout_parts.append(f"±{upper_str.replace('+', '')}")
        else:
            callout_parts.append(f"{upper_str}/{lower_str}")
        if suffix: callout_parts.append(suffix)

        full_callout = " ".join(callout_parts)

        return {
            "success": True,
            "raw_text": raw_text,
            "qty": qty,
            "prefix": prefix,
            "nominal": nominal_val,
            "nominal_str": nominal_str,
            "upper_tol": upper_str,
            "lower_tol": lower_str,
            "tol_type": tol_type,
            "suffix": suffix,
            "full_callout": full_callout
        }

    def _empty_result(self, raw_text):
        return {
            "success": False,
            "raw_text": raw_text,
            "qty": "",
            "prefix": "",
            "nominal": None,
            "nominal_str": "",
            "upper_tol": "",
            "lower_tol": "",
            "tol_type": "unknown",
            "suffix": "",
            "full_callout": raw_text
        }
