// AutoScanText Canvas & OCR Controller
document.addEventListener('DOMContentLoaded', () => {
    // State
    const state = {
        fileId: null,
        filename: 'Drawing',
        pageCount: 1,
        currentPage: 0,
        pageWidth: 0,
        pageHeight: 0,
        image: null,
        
        // Transform (Pan & Zoom)
        scale: 1.0,
        panX: 0,
        panY: 0,
        
        // Mouse interaction
        isLeftDown: false,
        isPanning: false,
        isPanModeActive: false,
        startX: 0,
        startY: 0,
        currentX: 0,
        currentY: 0,
        panStartX: 0,
        panStartY: 0,
        
        // Extracted items
        rows: [],
        sortOrder: 'desc', // 'desc' = kết quả mới nhất ở trên đầu, 'asc' = từ cũ đến mới
        
        // Rotation (0, 90, 180, 270)
        pageRotation: 0,
        cropRotation: 0,
        
        // Global Constraints Settings (0, 0.0, 0.00, 0.000, 0.0000, 0.00000)
        globalConstraints: {
            mode: 'decimals',
            fixed_value: 0.1,
            decimals: { 0: 0.2, 1: 0.1, 2: 0.05, 3: 0.01, 4: 0.005, 5: 0.001 }
        },

        // Tùy chọn hiển thị tọa độ X, Y trên Canvas (Mặc định: TẮT theo yêu cầu để đỡ rối mắt)
        showCoordinates: localStorage.getItem('autoscan_show_coordinates') === 'true',

        // Tùy chọn kiểu đánh số thứ tự: 'bubble' (Bong bóng tròn QC) hoặc 'tag' (Thẻ nhãn chữ nhật)
        badgeStyle: localStorage.getItem('autoscan_badge_style') || 'bubble',
        bubblePosition: localStorage.getItem('autoscan_bubble_pos') || 'top-right',
        bubbleColor: localStorage.getItem('autoscan_bubble_color') || 'red',
        bubbleRadius: parseInt(localStorage.getItem('autoscan_bubble_radius') || '14', 10), // Bán kính mặc định 14px (đường kính 28px)
        bubbleScaleWithDrawing: localStorage.getItem('autoscan_bubble_scale_with_drawing') !== 'false', // Mặc định: Phóng to/thu nhỏ theo tỉ lệ bản vẽ khi Zoom

        // Blue Box Selection & Editing (Drag/Move & Resize)
        selectedRowId: null,
        hoveredHandle: null,
        isDraggingBox: false,
        isResizingBox: false,
        activeHandle: null,
        dragStartX: 0,
        dragStartY: 0,
        boxStart: null,
        hasBoxChanged: false,

        // Kéo rê Bong bóng Bubble tự do (Free Drag & Leader Line)
        isDraggingBubble: false,
        draggingBubbleRowId: null,
        bubbleDragStartX: 0,
        bubbleDragStartY: 0,
        bubbleStartPos: null
    };

    // DOM Elements
    const canvas = document.getElementById('mainCanvas');
    const ctx = canvas.getContext('2d');
    const viewport = document.getElementById('canvasViewport');
    const emptyState = document.getElementById('emptyState');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const loadingText = document.getElementById('loadingText');
    const resultsTableBody = document.getElementById('resultsTableBody');
    const tableEmptyState = document.getElementById('tableEmptyState');
    const itemCountBadge = document.getElementById('itemCountBadge');
    const tableScrollContainer = document.getElementById('tableScrollContainer');
    const scrollToTopBtn = document.getElementById('scrollToTopBtn');
    const sortOrderBtn = document.getElementById('sortOrderBtn');
    const sortOrderIcon = document.getElementById('sortOrderIcon');
    const sortOrderText = document.getElementById('sortOrderText');
    
    const docName = document.getElementById('docName');
    const pageNavContainer = document.getElementById('pageNavContainer');
    const pageIndicator = document.getElementById('pageIndicator');
    const prevPageBtn = document.getElementById('prevPageBtn');
    const nextPageBtn = document.getElementById('nextPageBtn');
    
    const zoomLevelText = document.getElementById('zoomLevelText');
    const zoomInBtn = document.getElementById('zoomInBtn');
    const zoomOutBtn = document.getElementById('zoomOutBtn');
    const fitScreenBtn = document.getElementById('fitScreenBtn');
    const resetZoomBtn = document.getElementById('resetZoomBtn');
    const panToolBtn = document.getElementById('panToolBtn');
    const toggleShowCoordsBtn = document.getElementById('toggleShowCoordsBtn');
    const coordsBadgeText = document.getElementById('coordsBadgeText');
    const toggleBadgeStyleBtn = document.getElementById('toggleBadgeStyleBtn');
    const badgeStyleIcon = document.getElementById('badgeStyleIcon');
    const bubbleSizeDecBtn = document.getElementById('bubbleSizeDecBtn');
    const bubbleSizeIncBtn = document.getElementById('bubbleSizeIncBtn');
    const modalBubbleSizeDecBtn = document.getElementById('modalBubbleSizeDecBtn');
    const modalBubbleSizeIncBtn = document.getElementById('modalBubbleSizeIncBtn');
    const modalBubbleSizeText = document.getElementById('modalBubbleSizeText');
    const bubbleScaleWithDrawingCheckbox = document.getElementById('bubbleScaleWithDrawingCheckbox');
    const showCoordsCheckbox = document.getElementById('showCoordsCheckbox');
    const bubblePositionSelect = document.getElementById('bubblePositionSelect');
    const bubbleColorSelect = document.getElementById('bubbleColorSelect');
    const bubbleOptionsContainer = document.getElementById('bubbleOptionsContainer');
    const bubblePreviewHint = document.getElementById('bubblePreviewHint');

    const rotatePdfBtn = document.getElementById('rotatePdfBtn');
    const pageRotationText = document.getElementById('pageRotationText');
    const rotateCropBtn = document.getElementById('rotateCropBtn');
    const cropRotationText = document.getElementById('cropRotationText');
    const rotateMenuBtn = document.getElementById('rotateMenuBtn');
    const rotateSubMenu = document.getElementById('rotateSubMenu');
    const dockRotationIndicator = document.getElementById('dockRotationIndicator');
    
    const pdfFileInput = document.getElementById('pdfFileInput');
    const pdfFileInput2 = document.getElementById('pdfFileInput2');
    const exportDropdownBtn = document.getElementById('exportDropdownBtn');
    const exportMenu = document.getElementById('exportMenu');
    const exportExcelBtn = document.getElementById('exportExcelBtn');
    const exportCsvBtn = document.getElementById('exportCsvBtn');
    const clearAllBtn = document.getElementById('clearAllBtn');
    const tableSearchInput = document.getElementById('tableSearchInput');
    
    // Unified Settings Modal Elements
    const unifiedSettingsModal = document.getElementById('unifiedSettingsModal');
    const openUnifiedSettingsBtn = document.getElementById('openUnifiedSettingsBtn');
    const closeUnifiedSettingsBtn = document.getElementById('closeUnifiedSettingsBtn');
    const cancelUnifiedSettingsBtn = document.getElementById('cancelUnifiedSettingsBtn');
    const saveAllSettingsBtn = document.getElementById('saveAllSettingsBtn');
    const settingsTabBtns = document.querySelectorAll('.settings-tab-btn');
    const headerSettingsDot = document.getElementById('headerSettingsDot');

    // Legacy / Tab badges & lists
    const globalSummaryBadge = document.getElementById('globalSummaryBadge');
    const previewModal = document.getElementById('previewModal');
    const previewImg = document.getElementById('previewImg');
    const adaptiveCountBadge = document.getElementById('adaptiveCountBadge');
    const exactRulesList = document.getElementById('exactRulesList');
    const genRulesList = document.getElementById('genRulesList');
    const toastContainer = document.getElementById('toastContainer');

    // Footer Elements
    const footerAiModelTrigger = document.getElementById('footerAiModelTrigger');
    const footerAiDot = document.getElementById('footerAiDot');
    const footerAiModelText = document.getElementById('footerAiModelText');
    const footerRotationStatus = document.getElementById('footerRotationStatus');
    const footerTolRuleSummary = document.getElementById('footerTolRuleSummary');
    const footerUsageTrigger = document.getElementById('footerUsageTrigger');

    // AI Vision Elements inside Tab 1
    const aiApiKeyInput = document.getElementById('aiApiKeyInput');
    const aiModelSelect = document.getElementById('aiModelSelect');
    const testAiKeyBtn = document.getElementById('testAiKeyBtn');
    const clearAiKeyBtn = document.getElementById('clearAiKeyBtn');
    const aiStatusDot = document.getElementById('aiStatusDot');
    const aiStatusDetail = document.getElementById('aiStatusDetail');
    const toggleAiKeyVisBtn = document.getElementById('toggleAiKeyVisBtn');
    const aiAutoScanBtn = document.getElementById('aiAutoScanBtn');

    // AI Usage Progress Bar Elements
    const aiUsagePercentText = document.getElementById('aiUsagePercentText');
    const aiUsageProgressBar = document.getElementById('aiUsageProgressBar');
    const aiUsageReqText = document.getElementById('aiUsageReqText');
    const aiBillingTierSelect = document.getElementById('aiBillingTierSelect');
    const customQuotaContainer = document.getElementById('customQuotaContainer');
    const customRpdInput = document.getElementById('customRpdInput');
    const aiModalPercentBadge = document.getElementById('aiModalPercentBadge');
    const aiModalRpdText = document.getElementById('aiModalRpdText');
    const aiModalRpdBar = document.getElementById('aiModalRpdBar');
    const aiModalRpmText = document.getElementById('aiModalRpmText');
    const aiModalRpmBar = document.getElementById('aiModalRpmBar');
    const aiModalTokensText = document.getElementById('aiModalTokensText');
    const aiModalCostText = document.getElementById('aiModalCostText');
    const aiModalTierBadge = document.getElementById('aiModalTierBadge');

    // Toast Notification helper
    function showToast(message, type = 'success') {
        if (!toastContainer) return;
        const toast = document.createElement('div');
        toast.className = `px-4 py-2.5 rounded-lg shadow-xl text-xs font-medium flex items-center gap-2 transform transition-all duration-300 ease-out translate-y-2 opacity-0 pointer-events-auto border ${
            type === 'success' 
                ? 'bg-slate-800 text-emerald-300 border-emerald-500/50' 
                : 'bg-slate-800 text-amber-300 border-amber-500/50'
        }`;
        toast.innerHTML = `
            <i class="fa-solid ${type === 'success' ? 'fa-circle-check text-emerald-400' : 'fa-brain text-amber-400'}"></i>
            <span>${message}</span>
        `;
        toastContainer.appendChild(toast);
        requestAnimationFrame(() => {
            toast.classList.remove('translate-y-2', 'opacity-0');
        });
        setTimeout(() => {
            toast.classList.add('opacity-0', 'translate-y-2');
            setTimeout(() => toast.remove(), 300);
        }, 3200);
    }

    // Panel Resizer (Kéo chuột mở rộng bảng danh mục)
    const panelResizer = document.getElementById('panelResizer');
    const rightResultsPanel = document.getElementById('rightResultsPanel');
    
    // Khôi phục chiều rộng đã lưu nếu có
    const savedPanelWidth = localStorage.getItem('autoscan_panel_width');
    if (savedPanelWidth && rightResultsPanel) {
        const parsedW = parseInt(savedPanelWidth, 10);
        if (parsedW >= 420 && parsedW <= (window.innerWidth - 300)) {
            rightResultsPanel.style.width = `${parsedW}px`;
        }
    }

    if (panelResizer && rightResultsPanel) {
        let isResizingPanel = false;
        let startX = 0;
        let startWidth = 0;

        panelResizer.addEventListener('mousedown', (e) => {
            isResizingPanel = true;
            startX = e.clientX;
            startWidth = rightResultsPanel.offsetWidth;
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
            panelResizer.classList.add('bg-cyan-500');
            e.preventDefault();
        });

        window.addEventListener('mousemove', (e) => {
            if (!isResizingPanel) return;
            const deltaX = startX - e.clientX; // Kéo sang trái -> Tăng bề rộng panel phải
            const minW = 450;
            const maxW = Math.max(500, window.innerWidth - 350);
            const newWidth = Math.min(Math.max(startWidth + deltaX, minW), maxW);
            rightResultsPanel.style.width = `${newWidth}px`;
            resizeCanvas();
        });

        window.addEventListener('mouseup', () => {
            if (isResizingPanel) {
                isResizingPanel = false;
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
                panelResizer.classList.remove('bg-cyan-500');
                localStorage.setItem('autoscan_panel_width', rightResultsPanel.offsetWidth);
                resizeCanvas();
            }
        });
    }

    // Resize Canvas to fit viewport
    function resizeCanvas() {
        if (!viewport) return;
        canvas.width = viewport.clientWidth;
        canvas.height = viewport.clientHeight;
        render();
    }
    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

    // Render Canvas
    function render() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (!state.image) return;

        ctx.save();
        ctx.translate(state.panX, state.panY);
        ctx.scale(state.scale, state.scale);

        // 1. Ve anh ban ve
        ctx.drawImage(state.image, 0, 0, state.pageWidth, state.pageHeight);

        // 2. Ve cac o da crop truoc do (highlight overlay kem toa do X, Y)
        state.rows.forEach(r => {
            if (r.page === state.currentPage && r.raw_box) {
                const isSelected = (r.id === state.selectedRowId);
                const box = r.raw_box;

                if (isSelected) {
                    // Box dang duoc chon de chinh sua (keo tha / resize)
                    ctx.fillStyle = 'rgba(6, 182, 212, 0.22)';
                    ctx.strokeStyle = '#06b6d4';
                    ctx.lineWidth = 2.5 / state.scale;
                    ctx.fillRect(box.x, box.y, box.w, box.h);
                    ctx.strokeRect(box.x, box.y, box.w, box.h);

                    // Vien net dut tao hieu ung active
                    ctx.strokeStyle = '#ffffff';
                    ctx.lineWidth = 1 / state.scale;
                    ctx.setLineDash([4 / state.scale, 3 / state.scale]);
                    ctx.strokeRect(box.x, box.y, box.w, box.h);
                    ctx.setLineDash([]);

                    // Ve 8 resize handles
                    const handleSize = 8 / state.scale;
                    const handles = getBoxHandles(box);
                    for (const [key, pos] of Object.entries(handles)) {
                        ctx.fillStyle = (state.hoveredHandle === key) ? '#22d3ee' : '#ffffff';
                        ctx.strokeStyle = '#0891b2';
                        ctx.lineWidth = 1.5 / state.scale;
                        ctx.fillRect(pos.x - handleSize / 2, pos.y - handleSize / 2, handleSize, handleSize);
                        ctx.strokeRect(pos.x - handleSize / 2, pos.y - handleSize / 2, handleSize, handleSize);
                    }

                    // Nhan active hien thi dang chinh sua
                    const labelText = state.showCoordinates 
                        ? `✏️ #${r.id} (${Math.round(box.x)}, ${Math.round(box.y)}) [${Math.round(box.w)}x${Math.round(box.h)}]`
                        : `✏️ #${r.id} [${Math.round(box.w)}x${Math.round(box.h)}]`;
                    ctx.font = `bold ${Math.max(10, 11 / state.scale)}px monospace`;
                    const pad = 4 / state.scale;
                    const textWidth = ctx.measureText(labelText).width;

                    ctx.fillStyle = '#0e7490';
                    ctx.fillRect(box.x, box.y - 20 / state.scale, textWidth + pad * 2, 19 / state.scale);
                    ctx.strokeStyle = '#22d3ee';
                    ctx.strokeRect(box.x, box.y - 20 / state.scale, textWidth + pad * 2, 19 / state.scale);
                    ctx.fillStyle = '#ffffff';
                    ctx.fillText(labelText, box.x + pad, box.y - 6 / state.scale);

                } else {
                    // Box thuong (chua chon)
                    // Neu da co Bubble va chi do: An Blue Box giup ban ve sach dep chuan Inspection
                    if (state.badgeStyle !== 'bubble') {
                        ctx.fillStyle = 'rgba(59, 130, 246, 0.15)';
                        ctx.strokeStyle = '#3b82f6';
                        ctx.lineWidth = 2 / state.scale;
                        ctx.fillRect(box.x, box.y, box.w, box.h);
                        ctx.strokeRect(box.x, box.y, box.w, box.h);
                    }
                }

                // =========================================================================
                // HIỂN THỊ BONG BÓNG BUBBLE (QC BALLOON) HOẶC THẺ NHÃN (TAG)
                // =========================================================================
                if (state.badgeStyle === 'bubble') {
                    // 1. Tọa độ tâm bong bóng & Bán kính (Scale theo bản vẽ hoặc Khóa size màn hình)
                    const baseR = state.bubbleRadius || 14;
                    const bubbleRadius = state.bubbleScaleWithDrawing ? baseR : (baseR / state.scale);

                    const bc = getBubbleCenter(r, box);
                    const bx = bc.x;
                    const by = bc.y;

                    // 2. Bảng màu Bubble (QC Red, Cyan, Amber, Emerald)
                    let strokeCol = '#ef4444'; // Red default
                    let fillCol = '#ffffff';
                    let textCol = '#dc2626';

                    if (state.bubbleColor === 'cyan') {
                        strokeCol = '#06b6d4';
                        textCol = '#0891b2';
                    } else if (state.bubbleColor === 'amber') {
                        strokeCol = '#f59e0b';
                        textCol = '#d97706';
                    } else if (state.bubbleColor === 'emerald') {
                        strokeCol = '#10b981';
                        textCol = '#059669';
                    }

                    // 3. Vẽ Dây Đính Kèm (Leader Line) nối từ mép Bong Bóng tới mép Text/Kích thước
                    const targetX = Math.max(box.x, Math.min(box.x + box.w, bx));
                    const targetY = Math.max(box.y, Math.min(box.y + box.h, by));
                    const ldx = targetX - bx;
                    const ldy = targetY - by;
                    const dist = Math.hypot(ldx, ldy);

                    const leaderLineWidth = state.bubbleScaleWithDrawing ? 1.6 : (1.6 / state.scale);
                    const dotRadius = state.bubbleScaleWithDrawing ? 2.5 : (2.5 / state.scale);
                    const lineWidth = state.bubbleScaleWithDrawing ? 2.0 : (2.0 / state.scale);

                    if (dist > bubbleRadius * 0.9) {
                        const startX = bx + (ldx / dist) * bubbleRadius;
                        const startY = by + (ldy / dist) * bubbleRadius;

                        ctx.save();
                        ctx.beginPath();
                        ctx.moveTo(startX, startY);
                        ctx.lineTo(targetX, targetY);
                        ctx.strokeStyle = isSelected ? '#06b6d4' : strokeCol;
                        ctx.lineWidth = leaderLineWidth;
                        ctx.stroke();

                        // Điểm chốt dây (Anchor dot) tròn nhỏ đính vào vị trí kích thước
                        ctx.beginPath();
                        ctx.arc(targetX, targetY, dotRadius, 0, Math.PI * 2);
                        ctx.fillStyle = isSelected ? '#06b6d4' : strokeCol;
                        ctx.fill();
                        ctx.restore();
                    }

                    // 4. Vẽ hình tròn Bong bóng Bubble (Scale đồng bộ theo zoom bản vẽ)
                    ctx.save();
                    ctx.beginPath();
                    ctx.arc(bx, by, bubbleRadius, 0, Math.PI * 2);
                    ctx.fillStyle = fillCol;
                    ctx.fill();
                    ctx.lineWidth = lineWidth;
                    ctx.strokeStyle = isSelected ? '#06b6d4' : strokeCol;
                    ctx.stroke();

                    // Hiệu ứng viền sáng nếu box đang được chọn (Selected)
                    if (isSelected) {
                        const ringOffset = state.bubbleScaleWithDrawing ? 3 : (3 / state.scale);
                        ctx.beginPath();
                        ctx.arc(bx, by, bubbleRadius + ringOffset, 0, Math.PI * 2);
                        ctx.strokeStyle = 'rgba(6, 182, 212, 0.7)';
                        ctx.lineWidth = state.bubbleScaleWithDrawing ? 1.5 : (1.5 / state.scale);
                        ctx.setLineDash([ringOffset, ringOffset]);
                        ctx.stroke();
                        ctx.setLineDash([]);
                    }

                    // 5. Vẽ số thứ tự bên trong Bubble
                    const fontSize = state.bubbleScaleWithDrawing 
                        ? Math.max(8, Math.round(bubbleRadius * 0.82))
                        : Math.max(7 / state.scale, Math.round(bubbleRadius * 0.82));
                    ctx.font = `bold ${fontSize}px sans-serif`;
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.fillStyle = isSelected ? '#0891b2' : textCol;
                    const textYOffset = state.bubbleScaleWithDrawing ? 0.5 : (0.5 / state.scale);
                    ctx.fillText(`${r.id}`, bx, by + textYOffset);
                    ctx.restore();

                    // 6. Nếu bật tọa độ X, Y thì vẽ thêm nhãn phụ bên cạnh
                    if (state.showCoordinates) {
                        const coordText = `(${Math.round(box.x)}, ${Math.round(box.y)})`;
                        const coordFont = state.bubbleScaleWithDrawing ? 10 : Math.round(10 / state.scale);
                        ctx.font = `bold ${coordFont}px monospace`;
                        const pad = state.bubbleScaleWithDrawing ? 3 : (3 / state.scale);
                        const textW = ctx.measureText(coordText).width;
                        const labelH = state.bubbleScaleWithDrawing ? 16 : (16 / state.scale);
                        const labelY = state.bubbleScaleWithDrawing ? (by - 8) : (by - 8 / state.scale);
                        ctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
                        ctx.fillRect(bx + bubbleRadius + pad, labelY, textW + pad * 2, labelH);
                        ctx.fillStyle = '#67e8f9';
                        ctx.fillText(coordText, bx + bubbleRadius + pad * 2, by + (state.bubbleScaleWithDrawing ? 4 : (4 / state.scale)));
                    }

                } else if (!isSelected) {
                    // Kiểu Thẻ Nhãn Chữ Nhật (Tag Style) khi chưa chọn
                    const labelText = state.showCoordinates 
                        ? `#${r.id} (${Math.round(box.x)}, ${Math.round(box.y)})`
                        : `#${r.id}`;
                    ctx.font = `bold ${Math.max(10, 11 / state.scale)}px monospace`;
                    const pad = 4 / state.scale;
                    const textWidth = ctx.measureText(labelText).width;

                    ctx.fillStyle = '#1e3a8a';
                    ctx.fillRect(box.x, box.y - 18 / state.scale, textWidth + pad * 2, 18 / state.scale);
                    ctx.strokeStyle = '#3b82f6';
                    ctx.strokeRect(box.x, box.y - 18 / state.scale, textWidth + pad * 2, 18 / state.scale);
                    ctx.fillStyle = '#67e8f9';
                    ctx.fillText(labelText, box.x + pad, box.y - 5 / state.scale);
                }
            }
        });

        // 3. Ve o crop dang keo moi (Active selection box)
        if (state.isLeftDown) {
            const x = Math.min(state.startX, state.currentX);
            const y = Math.min(state.startY, state.currentY);
            const w = Math.abs(state.currentX - state.startX);
            const h = Math.abs(state.currentY - state.startY);

            // Glowing cyan box
            ctx.fillStyle = 'rgba(6, 182, 212, 0.2)';
            ctx.strokeStyle = '#22d3ee';
            ctx.lineWidth = 2 / state.scale;
            ctx.setLineDash([4 / state.scale, 2 / state.scale]);
            ctx.fillRect(x, y, w, h);
            ctx.strokeRect(x, y, w, h);
            ctx.setLineDash([]);

            // Nhan toa do thuc thoi (nếu tắt tọa độ: chỉ hiện kích thước WxH)
            const liveCoord = state.showCoordinates 
                ? `X:${Math.round(x)} Y:${Math.round(y)} (${Math.round(w)}x${Math.round(h)})`
                : `[${Math.round(w)}x${Math.round(h)}]`;
            ctx.font = `bold ${Math.max(10, 11 / state.scale)}px monospace`;
            const liveWidth = ctx.measureText(liveCoord).width;
            ctx.fillStyle = 'rgba(15, 23, 42, 0.9)';
            ctx.fillRect(x, y - 20 / state.scale, liveWidth + 8 / state.scale, 18 / state.scale);
            ctx.fillStyle = '#22d3ee';
            ctx.fillText(liveCoord, x + 4 / state.scale, y - 6 / state.scale);
        }

        ctx.restore();
    }

    // Helper: Tính tọa độ tâm của Bong bóng Bubble (tự do do người dùng kéo rê, hoặc theo vị trí mặc định)
    function getBubbleCenter(r, box) {
        if (r && r.bubble_pos && typeof r.bubble_pos.x === 'number' && typeof r.bubble_pos.y === 'number') {
            return { x: r.bubble_pos.x, y: r.bubble_pos.y };
        }
        // Vị trí mặc định: Đặt lệch khỏi góc box một khoảng tỷ lệ theo cỡ bong bóng
        const baseR = state.bubbleRadius || 14;
        const offset = state.bubbleScaleWithDrawing ? (baseR * 1.6) : ((baseR * 1.6) / state.scale);
        let bx = box.x + box.w + offset;
        let by = box.y - offset * 0.5;

        if (state.bubblePosition === 'top-left') {
            bx = box.x - offset;
            by = box.y - offset * 0.5;
        } else if (state.bubblePosition === 'bottom-right') {
            bx = box.x + box.w + offset;
            by = box.y + box.h + offset * 0.5;
        } else if (state.bubblePosition === 'bottom-left') {
            bx = box.x - offset;
            by = box.y + box.h + offset * 0.5;
        }

        return { x: bx, y: by };
    }

    // Helper: Kiểm tra một điểm pt (x, y) trên ảnh có nằm trong vòng tròn Bong bóng của row không
    function isPointInBubble(pt, r) {
        if (state.badgeStyle !== 'bubble' || !r || !r.raw_box) return false;
        const bc = getBubbleCenter(r, r.raw_box);
        const baseR = state.bubbleRadius || 14;
        const hitRadius = state.bubbleScaleWithDrawing ? (baseR + 4) : ((baseR + 4) / state.scale);
        const distSq = (pt.x - bc.x) * (pt.x - bc.x) + (pt.y - bc.y) * (pt.y - bc.y);
        return distSq <= hitRadius * hitRadius;
    }

    // Helper functions exported to window/scope
    function getBoxHandles(box) {
        const { x, y, w, h } = box;
        const midX = x + w / 2;
        const midY = y + h / 2;
        return {
            nw: { x: x, y: y, cursor: 'nwse-resize' },
            n:  { x: midX, y: y, cursor: 'ns-resize' },
            ne: { x: x + w, y: y, cursor: 'nesw-resize' },
            e:  { x: x + w, y: midY, cursor: 'ew-resize' },
            se: { x: x + w, y: y + h, cursor: 'nwse-resize' },
            s:  { x: midX, y: y + h, cursor: 'ns-resize' },
            sw: { x: x, y: y + h, cursor: 'nesw-resize' },
            w:  { x: x, y: midY, cursor: 'ew-resize' }
        };
    }

    function isPointInBox(pt, box) {
        return (pt.x >= box.x && pt.x <= box.x + box.w &&
                pt.y >= box.y && pt.y <= box.y + box.h);
    }

    // Tính tỷ lệ trùng lặp (Overlap ratio / IoU) giữa 2 bounding box
    function calculateBoxOverlap(box1, box2) {
        const x1 = Math.max(box1.x, box2.x);
        const y1 = Math.max(box1.y, box2.y);
        const x2 = Math.min(box1.x + box1.w, box2.x + box2.w);
        const y2 = Math.min(box1.y + box1.h, box2.y + box2.h);

        const interW = Math.max(0, x2 - x1);
        const interH = Math.max(0, y2 - y1);
        const interArea = interW * interH;
        if (interArea <= 0) return 0;

        const area1 = box1.w * box1.h;
        const area2 = box2.w * box2.h;
        const minArea = Math.min(area1, area2);
        const unionArea = area1 + area2 - interArea;

        // Trả về cả IoU và tỷ lệ chồng lấp so với box nhỏ hơn
        return Math.max(interArea / (unionArea || 1), interArea / (minArea || 1));
    }

    function getHitHandle(pt, box) {
        const handles = getBoxHandles(box);
        const hitRadius = 8 / state.scale;
        for (const [key, pos] of Object.entries(handles)) {
            if (Math.abs(pt.x - pos.x) <= hitRadius && Math.abs(pt.y - pos.y) <= hitRadius) {
                return { name: key, cursor: pos.cursor };
            }
        }
        return null;
    }

    // Convert Screen coordinates to Image coordinates
    function screenToImage(screenX, screenY) {
        const rect = canvas.getBoundingClientRect();
        const clientX = screenX - rect.left;
        const clientY = screenY - rect.top;
        const imgX = (clientX - state.panX) / state.scale;
        const imgY = (clientY - state.panY) / state.scale;
        return { x: imgX, y: imgY };
    }

    // Fit image to screen
    function fitToScreen() {
        if (!state.image) return;
        const pad = 40;
        const scaleX = (canvas.width - pad) / state.pageWidth;
        const scaleY = (canvas.height - pad) / state.pageHeight;
        state.scale = Math.min(scaleX, scaleY, 1.5);
        state.panX = (canvas.width - state.pageWidth * state.scale) / 2;
        state.panY = (canvas.height - state.pageHeight * state.scale) / 2;
        updateZoomText();
        render();
    }

    function updateZoomText() {
        zoomLevelText.textContent = `${Math.round(state.scale * 100)}%`;
    }

    // Pan Mode Toggle function
    function setPanMode(active) {
        state.isPanModeActive = active;
        if (!panToolBtn) return;
        if (active) {
            panToolBtn.classList.add('bg-blue-600', 'text-white', 'shadow-md', 'shadow-blue-500/30');
            panToolBtn.classList.remove('text-slate-300', 'hover:bg-slate-700');
            if (!state.isLeftDown) {
                viewport.style.cursor = 'grab';
            }
        } else {
            panToolBtn.classList.remove('bg-blue-600', 'text-white', 'shadow-md', 'shadow-blue-500/30');
            panToolBtn.classList.add('text-slate-300', 'hover:bg-slate-700');
            if (!state.isLeftDown && !isCtrlPressed && !isSpacePressed) {
                viewport.style.cursor = 'crosshair';
            }
        }
    }

    if (panToolBtn) {
        panToolBtn.addEventListener('click', () => {
            setPanMode(!state.isPanModeActive);
        });
    }

    // Key states for Pan modifiers (Ctrl, Space)
    let isCtrlPressed = false;
    let isSpacePressed = false;

    window.addEventListener('keydown', (e) => {
        // Phím H hoặc P để bật/tắt chế độ Pan nhanh
        if ((e.key === 'h' || e.key === 'H' || e.key === 'p' || e.key === 'P') && 
            e.target.tagName !== 'INPUT' && !e.target.isContentEditable) {
            setPanMode(!state.isPanModeActive);
            return;
        }

        if (e.key === 'Escape') {
            if (state.isPanModeActive) {
                setPanMode(false);
                return;
            }
            if (state.selectedRowId !== null) {
                state.selectedRowId = null;
                unhighlightTableRows();
                render();
                return;
            }
        }

        // Delete hoặc Backspace để xóa box đang chọn
        if ((e.key === 'Delete' || e.key === 'Backspace') && 
            e.target.tagName !== 'INPUT' && !e.target.isContentEditable) {
            if (state.selectedRowId !== null) {
                const idx = state.rows.findIndex(r => r.id === state.selectedRowId);
                if (idx !== -1) {
                    state.rows.splice(idx, 1);
                    state.selectedRowId = null;
                    renderTable();
                    render();
                    showToast('Đã xóa vùng quét kích thước', 'adaptive');
                    e.preventDefault();
                    return;
                }
            }
        }

        // Phím mũi tên (Arrow keys) để di chuyển vi chỉnh (nudge) Box đang chọn
        if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key) && 
            e.target.tagName !== 'INPUT' && !e.target.isContentEditable) {
            if (state.selectedRowId !== null) {
                const selRow = state.rows.find(r => r.id === state.selectedRowId);
                if (selRow && selRow.raw_box) {
                    const step = e.shiftKey ? 10 : 2;
                    if (e.key === 'ArrowLeft') selRow.raw_box.x = Math.max(0, selRow.raw_box.x - step);
                    if (e.key === 'ArrowRight') selRow.raw_box.x = Math.min(state.pageWidth - selRow.raw_box.w, selRow.raw_box.x + step);
                    if (e.key === 'ArrowUp') selRow.raw_box.y = Math.max(0, selRow.raw_box.y - step);
                    if (e.key === 'ArrowDown') selRow.raw_box.y = Math.min(state.pageHeight - selRow.raw_box.h, selRow.raw_box.y + step);
                    render();
                    e.preventDefault();
                    return;
                }
            }
        }

        if (e.key === 'Control' || e.ctrlKey) {
            isCtrlPressed = true;
            if (!state.isLeftDown && state.image && !state.isPanning) {
                viewport.style.cursor = 'grab';
            }
        }
        if (e.code === 'Space' && e.target.tagName !== 'INPUT' && !e.target.isContentEditable) {
            isSpacePressed = true;
            if (!state.isLeftDown && state.image && !state.isPanning) {
                viewport.style.cursor = 'grab';
            }
        }
    });

    window.addEventListener('keyup', (e) => {
        if (e.key === 'Control') {
            isCtrlPressed = false;
            if (!state.isPanning) {
                viewport.style.cursor = (state.isPanModeActive || isSpacePressed) ? 'grab' : 'crosshair';
            }
        }
        if (e.code === 'Space') {
            isSpacePressed = false;
            if (!state.isPanning) {
                viewport.style.cursor = (state.isPanModeActive || isCtrlPressed) ? 'grab' : 'crosshair';
            }
        }
    });

    // Canvas Mouse Events: Selection, Move, Resize handles, or New Crop
    viewport.addEventListener('mousedown', (e) => {
        if (!state.image) return;
        
        // Pan khi: Bật nút Pan Mode trên menu, hoặc đè Ctrl, hoặc Chuột phải (button 2), hoặc giữ Space
        if (state.isPanModeActive || e.ctrlKey || isCtrlPressed || e.button === 2 || isSpacePressed) {
            state.isPanning = true;
            state.panStartX = e.clientX - state.panX;
            state.panStartY = e.clientY - state.panY;
            viewport.style.cursor = 'grabbing';
            e.preventDefault();
            return;
        }

        // Chuột trái (button 0)
        if (e.button === 0) {
            const pt = screenToImage(e.clientX, e.clientY);

            // 0. Kiểm tra nếu bấm vào Bong bóng Bubble (Ưu tiên kéo rê Bong bóng tự do)
            if (state.badgeStyle === 'bubble') {
                let clickedBubbleRow = null;
                // Ưu tiên bubble của box đang chọn trước
                if (state.selectedRowId !== null) {
                    const curSel = state.rows.find(r => r.id === state.selectedRowId && r.page === state.currentPage);
                    if (curSel && isPointInBubble(pt, curSel)) {
                        clickedBubbleRow = curSel;
                    }
                }
                // Nếu chưa trúng, duyệt toàn bộ các bubble khác trên trang
                if (!clickedBubbleRow) {
                    for (let i = state.rows.length - 1; i >= 0; i--) {
                        const r = state.rows[i];
                        if (r.page === state.currentPage && isPointInBubble(pt, r)) {
                            clickedBubbleRow = r;
                            break;
                        }
                    }
                }

                if (clickedBubbleRow) {
                    state.selectedRowId = clickedBubbleRow.id;
                    state.isDraggingBubble = true;
                    state.draggingBubbleRowId = clickedBubbleRow.id;
                    state.bubbleDragStartX = pt.x;
                    state.bubbleDragStartY = pt.y;
                    const curBc = getBubbleCenter(clickedBubbleRow, clickedBubbleRow.raw_box);
                    state.bubbleStartPos = { x: curBc.x, y: curBc.y };
                    viewport.style.cursor = 'grabbing';
                    highlightTableRow(clickedBubbleRow.id);
                    render();
                    e.preventDefault();
                    return;
                }
            }

            // 1. Kiểm tra nếu đang có box được chọn và người dùng bấm trúng Resize Handle
            if (state.selectedRowId !== null) {
                const selRow = state.rows.find(r => r.id === state.selectedRowId && r.page === state.currentPage);
                if (selRow && selRow.raw_box) {
                    const hit = getHitHandle(pt, selRow.raw_box);
                    if (hit) {
                        state.isResizingBox = true;
                        state.activeHandle = hit.name;
                        state.dragStartX = pt.x;
                        state.dragStartY = pt.y;
                        state.boxStart = { ...selRow.raw_box };
                        state.hasBoxChanged = false;
                        viewport.style.cursor = hit.cursor;
                        e.preventDefault();
                        return;
                    }
                }
            }

            // 2. Kiểm tra nếu người dùng bấm vào bên trong một Box xanh đã có (ưu tiên box đang chọn trước)
            let clickedRow = null;
            if (state.selectedRowId !== null) {
                const curSel = state.rows.find(r => r.id === state.selectedRowId && r.page === state.currentPage);
                if (curSel && curSel.raw_box && isPointInBox(pt, curSel.raw_box)) {
                    clickedRow = curSel;
                }
            }
            // Nếu không trúng box đang chọn, tìm trong các box khác trên trang (duyệt từ mới nhất đến cũ nhất)
            if (!clickedRow) {
                for (let i = state.rows.length - 1; i >= 0; i--) {
                    const r = state.rows[i];
                    if (r.page === state.currentPage && r.raw_box && isPointInBox(pt, r.raw_box)) {
                        clickedRow = r;
                        break;
                    }
                }
            }

            if (clickedRow) {
                // Chọn box và bắt đầu chế độ Kéo thả di chuyển (Drag/Move)
                state.selectedRowId = clickedRow.id;
                state.isDraggingBox = true;
                state.dragStartX = pt.x;
                state.dragStartY = pt.y;
                state.boxStart = { ...clickedRow.raw_box };
                state.hasBoxChanged = false;
                viewport.style.cursor = 'move';
                render();
                highlightTableRow(clickedRow.id);
                e.preventDefault();
                return;
            }

            // 3. Nếu bấm vào vùng trống: Bỏ chọn box hiện tại và bắt đầu kéo vùng Crop mới
            if (state.selectedRowId !== null) {
                state.selectedRowId = null;
                unhighlightTableRows();
            }
            state.isLeftDown = true;
            state.startX = pt.x;
            state.startY = pt.y;
            state.currentX = pt.x;
            state.currentY = pt.y;
            render();
        }
    });

    // Double click để đưa Bong bóng về vị trí mặc định
    viewport.addEventListener('dblclick', (e) => {
        if (!state.image || state.badgeStyle !== 'bubble') return;
        const pt = screenToImage(e.clientX, e.clientY);
        for (let i = state.rows.length - 1; i >= 0; i--) {
            const r = state.rows[i];
            if (r.page === state.currentPage && isPointInBubble(pt, r)) {
                r.bubble_pos = null;
                render();
                showToast(`Đã khôi phục vị trí bong bóng #${r.id} về mặc định`, 'info');
                e.preventDefault();
                return;
            }
        }
    });

    window.addEventListener('mousemove', (e) => {
        if (state.isPanning) {
            state.panX = e.clientX - state.panStartX;
            state.panY = e.clientY - state.panStartY;
            render();
            return;
        }

        const pt = screenToImage(e.clientX, e.clientY);

        // A. Đang kéo rê Bong bóng Bubble tự do
        if (state.isDraggingBubble && state.draggingBubbleRowId !== null) {
            const dx = pt.x - state.bubbleDragStartX;
            const dy = pt.y - state.bubbleDragStartY;
            const r = state.rows.find(row => row.id === state.draggingBubbleRowId);
            if (r && state.bubbleStartPos) {
                r.bubble_pos = {
                    x: state.bubbleStartPos.x + dx,
                    y: state.bubbleStartPos.y + dy
                };
                render();
            }
            return;
        }

        // B. Đang kéo di chuyển Box
        if (state.isDraggingBox && state.selectedRowId !== null) {
            const dx = pt.x - state.dragStartX;
            const dy = pt.y - state.dragStartY;
            const selRow = state.rows.find(r => r.id === state.selectedRowId);
            if (selRow && selRow.raw_box && state.boxStart) {
                const oldX = selRow.raw_box.x;
                const oldY = selRow.raw_box.y;
                const newX = Math.max(0, Math.min(state.pageWidth - state.boxStart.w, state.boxStart.x + dx));
                const newY = Math.max(0, Math.min(state.pageHeight - state.boxStart.h, state.boxStart.y + dy));
                const deltaX = newX - oldX;
                const deltaY = newY - oldY;

                selRow.raw_box.x = newX;
                selRow.raw_box.y = newY;

                // Dịch chuyển Bong bóng đi cùng khi Box di chuyển
                if (selRow.bubble_pos) {
                    selRow.bubble_pos.x += deltaX;
                    selRow.bubble_pos.y += deltaY;
                }

                if (Math.abs(dx) > 1 || Math.abs(dy) > 1) {
                    state.hasBoxChanged = true;
                }
                render();
            }
            return;
        }

        // C. Đang kéo co giãn (Resize) Box bằng Handles
        if (state.isResizingBox && state.selectedRowId !== null) {
            const dx = pt.x - state.dragStartX;
            const dy = pt.y - state.dragStartY;
            const selRow = state.rows.find(r => r.id === state.selectedRowId);
            if (selRow && selRow.raw_box && state.boxStart) {
                const b = { ...state.boxStart };
                const handle = state.activeHandle;

                // Điều chỉnh theo handle tương ứng
                if (handle.includes('e')) {
                    b.w = Math.max(10, state.boxStart.w + dx);
                }
                if (handle.includes('s')) {
                    b.h = Math.max(10, state.boxStart.h + dy);
                }
                if (handle.includes('w')) {
                    const proposedW = state.boxStart.w - dx;
                    if (proposedW >= 10) {
                        b.x = state.boxStart.x + dx;
                        b.w = proposedW;
                    }
                }
                if (handle.includes('n')) {
                    const proposedH = state.boxStart.h - dy;
                    if (proposedH >= 10) {
                        b.y = state.boxStart.y + dy;
                        b.h = proposedH;
                    }
                }

                // Giới hạn trong kích thước trang
                b.x = Math.max(0, Math.min(state.pageWidth - b.w, b.x));
                b.y = Math.max(0, Math.min(state.pageHeight - b.h, b.y));

                if (Math.abs(dx) > 1 || Math.abs(dy) > 1) {
                    state.hasBoxChanged = true;
                }

                selRow.raw_box = b;
                render();
            }
            return;
        }

        // D. Đang kéo vẽ ô Crop mới
        if (state.isLeftDown) {
            state.currentX = pt.x;
            state.currentY = pt.y;
            render();
            return;
        }

        // E. Di chuột tự do (Hover) -> Cập nhật Cursor phù hợp
        if (!state.isPanModeActive && !isCtrlPressed && !isSpacePressed) {
            let cursorSet = false;

            // 1. Hover trên Bong bóng Bubble -> Cursor 'grab'
            if (state.badgeStyle === 'bubble') {
                for (let i = state.rows.length - 1; i >= 0; i--) {
                    const r = state.rows[i];
                    if (r.page === state.currentPage && isPointInBubble(pt, r)) {
                        viewport.style.cursor = 'grab';
                        cursorSet = true;
                        break;
                    }
                }
            }

            // 2. Hover trên resize handles của box đang chọn
            if (!cursorSet && state.selectedRowId !== null) {
                const selRow = state.rows.find(r => r.id === state.selectedRowId && r.page === state.currentPage);
                if (selRow && selRow.raw_box) {
                    const hit = getHitHandle(pt, selRow.raw_box);
                    if (hit) {
                        viewport.style.cursor = hit.cursor;
                        if (state.hoveredHandle !== hit.name) {
                            state.hoveredHandle = hit.name;
                            render();
                        }
                        cursorSet = true;
                    } else if (state.hoveredHandle !== null) {
                        state.hoveredHandle = null;
                        render();
                    }
                }
            }

            // 3. Hover trên thân box (đang chọn -> move, chưa chọn -> pointer)
            if (!cursorSet) {
                let hoveredOnBox = false;
                for (let i = state.rows.length - 1; i >= 0; i--) {
                    const r = state.rows[i];
                    if (r.page === state.currentPage && r.raw_box && isPointInBox(pt, r.raw_box)) {
                        hoveredOnBox = true;
                        if (r.id === state.selectedRowId) {
                            viewport.style.cursor = 'move';
                        } else {
                            viewport.style.cursor = 'pointer';
                        }
                        cursorSet = true;
                        break;
                    }
                }
            }

            // 4. Hover trên nền trống -> crosshair
            if (!cursorSet) {
                viewport.style.cursor = 'crosshair';
            }
        }
    });

    window.addEventListener('mouseup', async (e) => {
        if (state.isPanning) {
            state.isPanning = false;
            viewport.style.cursor = (state.isPanModeActive || isCtrlPressed || isSpacePressed || e.ctrlKey) ? 'grab' : 'crosshair';
            return;
        }

        // 0. Kết thúc kéo rê Bong bóng Bubble tự do
        if (state.isDraggingBubble) {
            state.isDraggingBubble = false;
            state.draggingBubbleRowId = null;
            state.bubbleStartPos = null;
            viewport.style.cursor = 'grab';
            render();
            return;
        }

        // 1. Kết thúc kéo di chuyển Box (Move)
        if (state.isDraggingBox) {
            state.isDraggingBox = false;
            viewport.style.cursor = 'move';
            if (state.hasBoxChanged && state.selectedRowId !== null) {
                const selRow = state.rows.find(r => r.id === state.selectedRowId);
                if (selRow && selRow.raw_box) {
                    // Kiểm tra xem sau khi kéo, box này có bị đè lên một box khác không
                    const otherRowIdx = state.rows.findIndex(r => 
                        r.id !== selRow.id && 
                        r.page === state.currentPage && 
                        r.raw_box && 
                        calculateBoxOverlap(selRow.raw_box, r.raw_box) > 0.6
                    );
                    if (otherRowIdx !== -1) {
                        const targetRow = state.rows[otherRowIdx];
                        showToast(`🔄 Nhập và cập nhật box vào mục #${targetRow.id}...`, 'adaptive');
                        // Xóa box đang kéo (để lại box đích và quét lại)
                        const selIdx = state.rows.findIndex(r => r.id === selRow.id);
                        state.rows.splice(selIdx, 1);
                        state.selectedRowId = targetRow.id;
                        await processCrop(
                            selRow.raw_box.x,
                            selRow.raw_box.y,
                            selRow.raw_box.w,
                            selRow.raw_box.h,
                            targetRow.crop_rotation || 0,
                            targetRow.id
                        );
                    } else {
                        showToast(`🔄 Đang quét lại OCR theo vị trí mới của #${selRow.id}...`, 'adaptive');
                        await processCrop(
                            selRow.raw_box.x,
                            selRow.raw_box.y,
                            selRow.raw_box.w,
                            selRow.raw_box.h,
                            selRow.crop_rotation || 0,
                            selRow.id
                        );
                    }
                }
            }
            state.hasBoxChanged = false;
            state.boxStart = null;
            return;
        }

        // 2. Kết thúc co giãn Box (Resize)
        if (state.isResizingBox) {
            state.isResizingBox = false;
            state.activeHandle = null;
            viewport.style.cursor = 'crosshair';
            if (state.hasBoxChanged && state.selectedRowId !== null) {
                const selRow = state.rows.find(r => r.id === state.selectedRowId);
                if (selRow && selRow.raw_box) {
                    showToast(`🔄 Đang quét lại OCR theo kích thước mới của #${selRow.id}...`, 'adaptive');
                    await processCrop(
                        selRow.raw_box.x,
                        selRow.raw_box.y,
                        selRow.raw_box.w,
                        selRow.raw_box.h,
                        selRow.crop_rotation || 0,
                        selRow.id
                    );
                }
            }
            state.hasBoxChanged = false;
            state.boxStart = null;
            return;
        }

        // 3. Kết thúc vẽ Crop mới
        if (state.isLeftDown && e.button === 0) {
            state.isLeftDown = false;
            const pt = screenToImage(e.clientX, e.clientY);
            state.currentX = pt.x;
            state.currentY = pt.y;
            render();

            const x0 = Math.min(state.startX, state.currentX);
            const y0 = Math.min(state.startY, state.currentY);
            const w = Math.abs(state.currentX - state.startX);
            const h = Math.abs(state.currentY - state.startY);

            // Chi scan neu vung crop lon hon 8x8 pixel
            if (w >= 8 && h >= 8) {
                const newBox = { x: x0, y: y0, w: w, h: h };
                // Kiem tra neu vung ve moi de len mot box da co (IoU > 0.5)
                let overlappedRow = null;
                for (let i = state.rows.length - 1; i >= 0; i--) {
                    const r = state.rows[i];
                    if (r.page === state.currentPage && r.raw_box) {
                        const overlap = calculateBoxOverlap(newBox, r.raw_box);
                        if (overlap > 0.5) {
                            overlappedRow = r;
                            break;
                        }
                    }
                }

                if (overlappedRow) {
                    // Cap nhat de len box da co thay vi tao 2 box trung nhau
                    showToast(`🔄 Quét lại và cập nhật cho kích thước #${overlappedRow.id}...`, 'adaptive');
                    await processCrop(x0, y0, w, h, overlappedRow.crop_rotation || 0, overlappedRow.id);
                } else {
                    await processCrop(x0, y0, w, h);
                }
            }
        }
    });

    // Disable context menu on right-click for canvas
    viewport.addEventListener('contextmenu', (e) => e.preventDefault());

    // Wheel Zoom centered at cursor
    viewport.addEventListener('wheel', (e) => {
        if (!state.image) return;
        e.preventDefault();

        const zoomFactor = e.deltaY < 0 ? 1.15 : 0.85;
        const newScale = Math.min(Math.max(0.1, state.scale * zoomFactor), 8.0);

        const rect = canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        // Zoom relative to mouse position
        state.panX = mouseX - (mouseX - state.panX) * (newScale / state.scale);
        state.panY = mouseY - (mouseY - state.panY) * (newScale / state.scale);
        state.scale = newScale;

        updateZoomText();
        render();
    }, { passive: false });

    // Floating Zoom Controls
    zoomInBtn.addEventListener('click', () => {
        state.scale = Math.min(state.scale * 1.25, 8.0);
        updateZoomText();
        render();
    });
    zoomOutBtn.addEventListener('click', () => {
        state.scale = Math.max(state.scale / 1.25, 0.1);
        updateZoomText();
        render();
    });
    fitScreenBtn.addEventListener('click', fitToScreen);
    resetZoomBtn.addEventListener('click', () => {
        state.scale = 1.0;
        state.panX = 0;
        state.panY = 0;
        updateZoomText();
        render();
    });

    // Helper: Bật/Tắt hiển thị nhãn tọa độ X, Y trên Canvas
    function setCoordinatesVisibility(visible, persist = true) {
        state.showCoordinates = !!visible;
        if (persist) {
            localStorage.setItem('autoscan_show_coordinates', state.showCoordinates ? 'true' : 'false');
        }
        
        // Cập nhật trạng thái hiển thị trên Dock button
        if (toggleShowCoordsBtn) {
            if (state.showCoordinates) {
                // Sáng rực rỡ lên biểu thị ON
                toggleShowCoordsBtn.className = 'px-2 py-1 text-cyan-300 bg-cyan-500/25 border border-cyan-400/70 shadow-sm shadow-cyan-500/40 rounded-lg transition flex items-center justify-center text-xs font-mono font-bold ring-1 ring-cyan-400/40';
                toggleShowCoordsBtn.title = 'Tọa độ (X, Y): Đang BẬT (Bấm để Tắt)';
            } else {
                // Tối mờ biểu thị OFF
                toggleShowCoordsBtn.className = 'px-2 py-1 text-slate-400 hover:text-slate-200 hover:bg-slate-800/80 rounded-lg transition flex items-center justify-center text-xs font-mono font-semibold border border-transparent';
                toggleShowCoordsBtn.title = 'Tọa độ (X, Y): Đang TẮT (Bấm để Bật)';
            }
        }

        // Cập nhật checkbox trong Cài đặt
        if (showCoordsCheckbox) {
            showCoordsCheckbox.checked = state.showCoordinates;
        }

        render();
    }

    // Helper: Chuyển đổi Kiểu Đánh Số Thứ Tự (Bubble vs Tag/Số)
    function setBadgeStyle(style, persist = true) {
        state.badgeStyle = (style === 'tag') ? 'tag' : 'bubble';
        if (persist) {
            localStorage.setItem('autoscan_badge_style', state.badgeStyle);
        }

        // Cập nhật nút trên Floating Dock: Đổi trực tiếp giữa icon Bubble ① và icon Dạng số #1
        if (toggleBadgeStyleBtn) {
            if (state.badgeStyle === 'bubble') {
                toggleBadgeStyleBtn.className = 'p-1 hover:bg-slate-800/80 rounded-lg transition flex items-center justify-center text-xs';
                toggleBadgeStyleBtn.innerHTML = '<span class="w-5 h-5 rounded-full border-2 border-red-500 bg-red-500/20 text-red-400 font-bold text-[11px] flex items-center justify-center font-mono shadow-sm shadow-red-500/30">①</span>';
                toggleBadgeStyleBtn.title = 'Kiểu đánh số: Bong bóng tròn Bubble ① (Bấm để đổi sang Dạng số #1)';
            } else {
                toggleBadgeStyleBtn.className = 'p-1 hover:bg-slate-800/80 rounded-lg transition flex items-center justify-center text-xs';
                toggleBadgeStyleBtn.innerHTML = '<span class="px-1.5 py-0.5 rounded bg-cyan-500/20 border border-cyan-400/60 text-cyan-300 font-mono font-bold text-[11px] flex items-center justify-center shadow-sm shadow-cyan-500/30">#1</span>';
                toggleBadgeStyleBtn.title = 'Kiểu đánh số: Dạng số #1 (Bấm để đổi sang Bong bóng tròn Bubble ①)';
            }
        }

        // Cập nhật Radio trong Modal Cài đặt
        const radio = document.querySelector(`input[name="badgeStyleRadio"][value="${state.badgeStyle}"]`);
        if (radio) radio.checked = true;

        if (bubbleOptionsContainer) {
            bubbleOptionsContainer.style.display = (state.badgeStyle === 'bubble') ? 'grid' : 'none';
        }
        if (bubblePreviewHint) {
            bubblePreviewHint.textContent = (state.badgeStyle === 'bubble') 
                ? '🔴 Bong bóng Bubble ① (Bản vẽ CAD / QC)' 
                : '🟦 Dạng số / Thẻ nhãn #1';
        }

        render();
    }

    // Helper: Cập nhật cấu hình nâng cao của Bubble (vị trí, màu sắc)
    function updateBubbleConfig(pos, color, persist = true) {
        if (pos) state.bubblePosition = pos;
        if (color) state.bubbleColor = color;
        if (persist) {
            localStorage.setItem('autoscan_bubble_pos', state.bubblePosition);
            localStorage.setItem('autoscan_bubble_color', state.bubbleColor);
        }
        if (bubblePositionSelect) bubblePositionSelect.value = state.bubblePosition;
        if (bubbleColorSelect) bubbleColorSelect.value = state.bubbleColor;
        render();
    }

    // Helper: Thay đổi kích thước Bong bóng Bubble (+ hoặc -)
    function changeBubbleSize(delta, persist = true) {
        let curR = state.bubbleRadius || 13;
        curR = Math.max(7, Math.min(28, curR + delta));
        state.bubbleRadius = curR;
        if (persist) {
            localStorage.setItem('autoscan_bubble_radius', state.bubbleRadius);
        }
        if (modalBubbleSizeText) {
            modalBubbleSizeText.textContent = `${state.bubbleRadius * 2}px`;
        }
        render();
        showToast(`Cỡ bóng: ${state.bubbleRadius * 2}px`, 'info');
    }

    // Khởi tạo trạng thái ban đầu của nút Tọa độ & Badge style
    setCoordinatesVisibility(state.showCoordinates, false);
    setBadgeStyle(state.badgeStyle, false);
    updateBubbleConfig(state.bubblePosition, state.bubbleColor, false);
    if (modalBubbleSizeText) {
        modalBubbleSizeText.textContent = `${(state.bubbleRadius || 13) * 2}px`;
    }

    // Sự kiện nút [+] và [-] tăng giảm size bong bóng (Trên Dock và Modal)
    if (bubbleSizeDecBtn) {
        bubbleSizeDecBtn.addEventListener('click', () => changeBubbleSize(-2));
    }
    if (bubbleSizeIncBtn) {
        bubbleSizeIncBtn.addEventListener('click', () => changeBubbleSize(+2));
    }
    if (modalBubbleSizeDecBtn) {
        modalBubbleSizeDecBtn.addEventListener('click', () => changeBubbleSize(-2));
    }
    if (modalBubbleSizeIncBtn) {
        modalBubbleSizeIncBtn.addEventListener('click', () => changeBubbleSize(+2));
    }

    // Sự kiện khi bấm nút Toggle Tọa độ trên thanh Floating Dock
    if (toggleShowCoordsBtn) {
        toggleShowCoordsBtn.addEventListener('click', () => {
            const nextState = !state.showCoordinates;
            setCoordinatesVisibility(nextState, true);
            if (nextState) {
                showToast('Tọa độ (X, Y): Đang BẬT', 'info');
            } else {
                showToast('Tọa độ (X, Y): Đang TẮT', 'success');
            }
        });
    }

    // Sự kiện khi bấm nút Toggle Badge Style (Bubble vs Tag) trên Floating Dock
    if (toggleBadgeStyleBtn) {
        toggleBadgeStyleBtn.addEventListener('click', () => {
            const nextStyle = (state.badgeStyle === 'bubble') ? 'tag' : 'bubble';
            setBadgeStyle(nextStyle, true);
            if (nextStyle === 'bubble') {
                showToast('Kiểu đánh số: Bong bóng tròn Bubble ①', 'success');
            } else {
                showToast('Kiểu đánh số: Dạng số #1', 'info');
            }
        });
    }

    // Lắng nghe thay đổi Radio kiểu đánh số trong Modal Cài đặt
    document.querySelectorAll('input[name="badgeStyleRadio"]').forEach(r => {
        r.addEventListener('change', (e) => {
            setBadgeStyle(e.target.value, true);
        });
    });

    if (bubblePositionSelect) {
        bubblePositionSelect.addEventListener('change', (e) => {
            updateBubbleConfig(e.target.value, null, true);
        });
    }

    if (bubbleColorSelect) {
        bubbleColorSelect.addEventListener('change', (e) => {
            updateBubbleConfig(null, e.target.value, true);
        });
    }

    // Sự kiện khi thay đổi checkbox trong Cài đặt
    if (showCoordsCheckbox) {
        showCoordsCheckbox.addEventListener('change', (e) => {
            setCoordinatesVisibility(e.target.checked, true);
        });
    }

    if (bubbleScaleWithDrawingCheckbox) {
        bubbleScaleWithDrawingCheckbox.checked = state.bubbleScaleWithDrawing;
        bubbleScaleWithDrawingCheckbox.addEventListener('change', (e) => {
            state.bubbleScaleWithDrawing = e.target.checked;
            localStorage.setItem('autoscan_bubble_scale_with_drawing', state.bubbleScaleWithDrawing ? 'true' : 'false');
            render();
            showToast(state.bubbleScaleWithDrawing 
                ? 'Đã BẬT: Bong bóng phóng to/thu nhỏ theo tỉ lệ bản vẽ' 
                : 'Đã TẮT: Khóa kích thước bong bóng cố định trên màn hình', 'info');
        });
    }

    // Helper: Đồng bộ chỉ số xoay trên Dock và Footer
    function updateRotationUI() {
        if (pageRotationText) pageRotationText.textContent = `${state.pageRotation}°`;
        if (cropRotationText) cropRotationText.textContent = `${state.cropRotation}°`;
        if (dockRotationIndicator) {
            dockRotationIndicator.textContent = `${state.pageRotation}°`;
            if (state.pageRotation !== 0 || state.cropRotation !== 0) {
                dockRotationIndicator.className = 'font-mono text-[10px] text-cyan-400 font-bold';
            } else {
                dockRotationIndicator.className = 'font-mono text-[10px] text-slate-400 font-bold';
            }
        }
        if (footerRotationStatus) {
            footerRotationStatus.textContent = `PDF: ${state.pageRotation}° • Crop: ${state.cropRotation}°`;
        }
    }

    // Toggle Rotate SubMenu
    if (rotateMenuBtn && rotateSubMenu) {
        rotateMenuBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            rotateSubMenu.classList.toggle('hidden');
            if (exportMenu) exportMenu.classList.add('hidden');
        });
    }

    // Toggle Export Dropdown Menu
    if (exportDropdownBtn && exportMenu) {
        exportDropdownBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            exportMenu.classList.toggle('hidden');
            if (rotateSubMenu) rotateSubMenu.classList.add('hidden');
        });
    }

    // Close Dropdown menus when clicking outside
    document.addEventListener('click', (e) => {
        if (rotateSubMenu && !rotateSubMenu.contains(e.target) && (!rotateMenuBtn || !rotateMenuBtn.contains(e.target))) {
            rotateSubMenu.classList.add('hidden');
        }
        if (exportMenu && !exportMenu.contains(e.target) && (!exportDropdownBtn || !exportDropdownBtn.contains(e.target))) {
            exportMenu.classList.add('hidden');
        }
    });

    // Rotate PDF Button (Xoay trang PDF 90 do)
    if (rotatePdfBtn) {
        rotatePdfBtn.addEventListener('click', async () => {
            if (!state.fileId) return;
            state.pageRotation = (state.pageRotation + 90) % 360;
            updateRotationUI();
            loadingText.textContent = `Đang xoay bản vẽ ${state.pageRotation}°...`;
            loadingOverlay.classList.remove('hidden');
            try {
                await loadPageImage(state.currentPage);
                showToast(`Đã xoay trang bản vẽ: ${state.pageRotation}°`, 'success');
            } catch (err) {
                alert('Lỗi xoay bản vẽ: ' + err.message);
            } finally {
                loadingOverlay.classList.add('hidden');
            }
        });
    }

    // Rotate Crop Button (Goc xoay vung crop khi OCR)
    if (rotateCropBtn) {
        rotateCropBtn.addEventListener('click', () => {
            state.cropRotation = (state.cropRotation + 90) % 360;
            updateRotationUI();
            if (state.cropRotation !== 0) {
                rotateCropBtn.classList.add('bg-cyan-600', 'text-white', 'shadow-md', 'shadow-cyan-500/30');
                rotateCropBtn.classList.remove('text-slate-300', 'hover:bg-slate-700');
                showToast(`Góc xoay crop OCR: ${state.cropRotation}° (Dành cho kích thước chữ dọc)`, 'success');
            } else {
                rotateCropBtn.classList.remove('bg-cyan-600', 'text-white', 'shadow-md', 'shadow-cyan-500/30');
                rotateCropBtn.classList.add('text-slate-300', 'hover:bg-slate-700');
                showToast(`Góc xoay crop: 0° (Mặc định ngang)`, 'info');
            }
        });
    }

    // File Upload Handler
    async function handleFileUpload(file) {
        if (!file || !file.name.toLowerCase().endsWith('.pdf')) {
            alert('Vui lòng chọn file định dạng .pdf');
            return;
        }

        loadingText.textContent = 'Đang tải và render bản vẽ PDF...';
        loadingOverlay.classList.remove('hidden');

        const formData = new FormData();
        formData.append('file', file);

        try {
            const resp = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.detail || 'Lỗi tải file');

            state.fileId = data.file_id;
            state.filename = data.filename;
            state.pageCount = data.page_count;
            state.currentPage = 0;
            state.pageRotation = 0;
            state.cropRotation = 0;
            updateRotationUI();
            if (rotateCropBtn) {
                rotateCropBtn.classList.remove('bg-cyan-600', 'text-white', 'shadow-md', 'shadow-cyan-500/30');
                rotateCropBtn.classList.add('text-slate-300', 'hover:bg-slate-700');
            }
            state.rows = [];
            renderTable();

            // Load trang 0
            await loadPageImage(0);

            // Update UI
            emptyState.classList.add('hidden');
            docName.textContent = data.filename;
            pageNavContainer.classList.remove('hidden');
            updatePageIndicator();

            exportExcelBtn.disabled = false;
            exportCsvBtn.disabled = false;
        } catch (err) {
            alert('Lỗi: ' + err.message);
        } finally {
            loadingOverlay.classList.add('hidden');
        }
    }

    pdfFileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) handleFileUpload(e.target.files[0]);
    });
    pdfFileInput2.addEventListener('change', (e) => {
        if (e.target.files.length > 0) handleFileUpload(e.target.files[0]);
    });

    // Drag & Drop PDF into viewport
    viewport.addEventListener('dragover', (e) => {
        e.preventDefault();
        viewport.classList.add('border-2', 'border-blue-500');
    });
    viewport.addEventListener('dragleave', () => {
        viewport.classList.remove('border-2', 'border-blue-500');
    });
    viewport.addEventListener('drop', (e) => {
        e.preventDefault();
        viewport.classList.remove('border-2', 'border-blue-500');
        if (e.dataTransfer.files.length > 0) {
            handleFileUpload(e.dataTransfer.files[0]);
        }
    });

    // Load Page Image
    async function loadPageImage(pageNum) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => {
                state.image = img;
                state.pageWidth = img.width;
                state.pageHeight = img.height;
                fitToScreen();
                resolve();
            };
            img.onerror = reject;
            img.src = `/api/page_image?file_id=${state.fileId}&page=${pageNum}&rotation=${state.pageRotation}&t=${Date.now()}`;
        });
    }

    // Page navigation
    function updatePageIndicator() {
        pageIndicator.textContent = `Trang ${state.currentPage + 1}/${state.pageCount}`;
        prevPageBtn.disabled = state.currentPage <= 0;
        nextPageBtn.disabled = state.currentPage >= state.pageCount - 1;
    }
    prevPageBtn.addEventListener('click', async () => {
        if (state.currentPage > 0) {
            state.currentPage--;
            updatePageIndicator();
            await loadPageImage(state.currentPage);
        }
    });
    nextPageBtn.addEventListener('click', async () => {
        if (state.currentPage < state.pageCount - 1) {
            state.currentPage++;
            updatePageIndicator();
            await loadPageImage(state.currentPage);
        }
    });

    // Process Crop Box to OCR
    async function processCrop(x, y, w, h, customCropRot = null, targetRowId = null) {
        if (!state.fileId) return;

        const cropRot = customCropRot !== null ? customCropRot : state.cropRotation;

        loadingText.textContent = cropRot !== 0 
            ? `Đang xoay ${cropRot}° & nhận diện ký tự...`
            : 'Đang nhận diện ký tự & phân tách dung sai...';
        loadingOverlay.classList.remove('hidden');

        // Toa do chuan hoa 0.0 -> 1.0
        const normBox = {
            x: x / state.pageWidth,
            y: y / state.pageHeight,
            width: w / state.pageWidth,
            height: h / state.pageHeight
        };

        try {
            const resp = await fetch('/api/crop-ocr', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    file_id: state.fileId,
                    page_num: state.currentPage,
                    crop_box: normBox,
                    global_constraints: state.globalConstraints,
                    page_rotation: state.pageRotation,
                    crop_rotation: cropRot
                })
            });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.detail || 'Lỗi xử lý OCR');

            const rowData = {
                thumbnail: data.thumbnail,
                qty: data.qty || '',
                prefix: data.prefix || '',
                nominal: data.nominal,
                nominal_str: data.nominal_str || (data.nominal !== null ? String(data.nominal) : ''),
                upper_tol: data.upper_tol || '',
                lower_tol: data.lower_tol || '',
                tol_type: data.tol_type || 'local',
                full_callout: data.full_callout || data.raw_text || '',
                raw_text: data.raw_text || '',
                raw_box: { x, y, w, h },
                box: data.box || { x, y, w, h },
                norm_box: data.norm_box || normBox,
                page: state.currentPage,
                crop_rotation: cropRot
            };

            if (targetRowId !== null) {
                const existingIdx = state.rows.findIndex(r => r.id === targetRowId);
                if (existingIdx !== -1) {
                    state.rows[existingIdx] = {
                        ...state.rows[existingIdx],
                        ...rowData
                    };
                    renderTable(false, existingIdx);
                    showToast(`✅ Đã quét lại và cập nhật mục #${targetRowId}`, 'success');
                }
            } else {
                const newRow = {
                    id: state.rows.length + 1,
                    page: state.currentPage,
                    ...rowData
                };
                state.rows.push(newRow);
                if (cropRot !== 0) {
                    showToast(`Đã quét kích thước với góc xoay ${cropRot}°`, 'success');
                }
                renderTable(true, state.rows.length - 1);
            }

            render(); // Ve them o crop overlay

        } catch (err) {
            alert('Lỗi: ' + err.message);
        } finally {
            loadingOverlay.classList.add('hidden');
        }
    }

    // Render Table Body
    function renderTable(autoScroll = false, highlightIdx = null) {
        resultsTableBody.innerHTML = '';
        itemCountBadge.textContent = `${state.rows.length} mục`;

        if (state.rows.length === 0) {
            tableEmptyState.classList.remove('hidden');
            return;
        }
        tableEmptyState.classList.add('hidden');

        // Lọc kết quả nếu người dùng nhập tìm kiếm
        const query = (tableSearchInput?.value || '').trim().toLowerCase();
        
        // Chuẩn bị danh sách hiển thị kèm original index trong state.rows
        let displayList = state.rows.map((row, originalIdx) => ({ row, originalIdx }));

        // 1. Áp dụng tìm kiếm nếu có
        if (query) {
            displayList = displayList.filter(({ row }) => {
                const searchableText = `${row.nominal_str || ''} ${row.full_callout || ''} ${row.raw_text || ''} ${row.prefix || ''} ${row.qty || ''}`.toLowerCase();
                return searchableText.includes(query);
            });
        }

        // 2. Sắp xếp: Mặc định 'desc' (kết quả mới nhất ở trên đầu, id lớn nhất ở trên)
        displayList.sort((a, b) => {
            if (state.sortOrder === 'desc') {
                return (b.row.id || b.originalIdx) - (a.row.id || a.originalIdx);
            } else {
                return (a.row.id || a.originalIdx) - (b.row.id || b.originalIdx);
            }
        });

        const displayCount = displayList.length;

        displayList.forEach(({ row, originalIdx }) => {
            const tr = document.createElement('tr');
            tr.className = 'hover:bg-slate-800/60 transition group border-b border-slate-800/50';
            if (highlightIdx === originalIdx) {
                tr.classList.add('bg-cyan-900/30', 'transition-colors', 'duration-700');
                setTimeout(() => {
                    tr.classList.remove('bg-cyan-900/30');
                }, 2500);
            }

            const isLearned = row.source && row.source.startsWith('adaptive');
            const isUserCorrected = row.user_corrected;

            const safeThumb = (row.thumbnail && row.thumbnail !== 'undefined') 
                ? row.thumbnail 
                : 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="64" height="36" fill="%23334155"><rect width="64" height="36" fill="%231e293b"/><text x="32" y="21" fill="%2364748b" font-size="10" text-anchor="middle" font-family="sans-serif">Crop</text></svg>';

            const box = row.box || row.raw_box || { x: 0, y: 0, w: 0, h: 0 };

            tr.innerHTML = `
                <td class="py-3 px-2 text-center text-slate-400 font-mono text-sm font-bold">${row.id || (originalIdx + 1)}</td>
                <td class="py-3 px-2 text-center">
                    <img src="${safeThumb}" class="w-16 h-9 object-contain bg-white rounded-md border border-slate-700 cursor-pointer hover:scale-150 transition-all origin-left shadow-md mx-auto" data-img="${safeThumb}" title="Nhấp để xem ảnh phóng to (X:${Math.round(box.x)}, Y:${Math.round(box.y)})">
                </td>
                <td class="py-3 px-3">
                    <div class="flex items-center space-x-1.5">
                        ${row.prefix ? `<span class="text-amber-400 font-bold font-mono text-base tracking-tight">${row.prefix}</span>` : ''}
                        <span class="editable-cell font-mono font-bold text-slate-50 text-base px-1.5 py-0.5 rounded hover:bg-slate-700/50 transition cursor-text" contenteditable="true" data-field="nominal_str" title="Kích thước danh nghĩa">${row.nominal_str}</span>
                        ${row.qty ? `<span class="text-xs text-slate-400 font-medium">(${row.qty})</span>` : ''}
                    </div>
                </td>
                <td class="py-3 px-2 text-center">
                    <div class="inline-flex flex-col text-xs font-mono font-semibold leading-tight bg-slate-950/50 px-2 py-1 rounded-md border border-slate-800">
                        <span class="editable-cell text-blue-400 hover:bg-blue-900/30 px-1 rounded transition text-xs font-bold" contenteditable="true" data-field="upper_tol" title="Dung sai trên (+)">${row.upper_tol || '-'}</span>
                        <span class="editable-cell text-rose-400 hover:bg-rose-900/30 px-1 rounded transition text-xs font-bold" contenteditable="true" data-field="lower_tol" title="Dung sai dưới (-)">${row.lower_tol || '-'}</span>
                    </div>
                </td>
                <td class="py-3 px-3">
                    <div class="flex items-center gap-2">
                        <span class="editable-cell font-mono font-bold text-cyan-300 text-base px-1.5 py-0.5 rounded hover:bg-slate-700/50 transition cursor-text block truncate max-w-[220px]" contenteditable="true" data-field="full_callout" title="${(row.full_callout || '').replace(/"/g, '&quot;')}">${row.full_callout || '-'}</span>
                        <span class="ai-learned-badge text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-amber-900/60 text-amber-300 border border-amber-600/70 shrink-0 ${(isLearned || isUserCorrected) ? '' : 'hidden'}" title="Đã học theo quy tắc AI">AI</span>
                        ${row.is_ai_vision ? `<span class="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-purple-900/70 text-purple-300 border border-purple-500/80 shrink-0 shadow-sm" title="Đã bóc tách bằng AI Vision">Vision</span>` : ''}
                    </div>
                </td>
                <td class="py-3 px-2 text-center whitespace-nowrap">
                    <div class="row-actions flex items-center justify-center space-x-1.5">
                        <button class="ai-inspect-btn text-slate-400 hover:text-purple-300 p-1.5 rounded hover:bg-slate-750 transition" title="Dùng AI Vision thẩm định & bóc tách lại kích thước này"><i class="fa-solid fa-wand-magic-sparkles text-sm"></i></button>
                        <button class="rotate-row-btn text-slate-400 hover:text-cyan-300 p-1.5 rounded hover:bg-slate-750 transition" title="Xoay ảnh 90° và quét lại OCR (Dành cho kích thước dọc)"><i class="fa-solid fa-arrow-rotate-right text-sm"></i></button>
                        <button class="text-slate-400 hover:text-rose-400 delete-btn p-1.5 rounded hover:bg-slate-750 transition" title="Xóa dòng"><i class="fa-solid fa-xmark text-base"></i></button>
                    </div>
                </td>
            `;

            // Thumbnail click preview
            const thumbImg = tr.querySelector('img');
            thumbImg.addEventListener('click', () => {
                previewImg.src = row.thumbnail;
                previewModal.classList.remove('hidden');
            });

            // AI Vision Deep Inspect row
            const aiInspectBtn = tr.querySelector('.ai-inspect-btn');
            if (aiInspectBtn) {
                aiInspectBtn.addEventListener('click', async () => {
                    const b = row.norm_box || (row.raw_box ? {
                        x: row.raw_box.x / state.pageWidth,
                        y: row.raw_box.y / state.pageHeight,
                        width: row.raw_box.w / state.pageWidth,
                        height: row.raw_box.h / state.pageHeight
                    } : null);
                    if (!b) return;

                    aiInspectBtn.innerHTML = '<i class="fa-solid fa-spinner animate-spin text-purple-400 text-xs"></i>';
                    try {
                        const curRot = row.crop_rotation || 0;
                        const resp = await fetch('/api/ai-vision/inspect-crop', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                file_id: state.fileId,
                                page_num: row.page !== undefined ? row.page : state.currentPage,
                                crop_box: b,
                                raw_ocr_hint: row.raw_text,
                                page_rotation: state.pageRotation,
                                crop_rotation: curRot
                            })
                        });
                        const data = await resp.json();
                        if (data.nominal_str || data.full_callout) {
                            state.rows[originalIdx] = {
                                ...state.rows[originalIdx],
                                ...data,
                                is_ai_vision: true
                            };
                            renderTable(false, originalIdx);
                            showToast(`✨ AI Vision: Đã giải mã xong #${row.id}: ${data.full_callout}`, 'success');
                        } else if (data.ai_error) {
                            showToast(`AI Vision: ${data.ai_error}`, 'warning');
                        }
                    } catch (err) {
                        showToast(`Lỗi AI Vision: ${err.message}`, 'error');
                    } finally {
                        aiInspectBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles text-xs"></i>';
                        checkAiVisionStatus();
                    }
                });
            }

            // Rotate row 90 deg and re-OCR
            const rotateRowBtn = tr.querySelector('.rotate-row-btn');
            if (rotateRowBtn) {
                rotateRowBtn.addEventListener('click', async () => {
                    if (row.raw_box) {
                        const curRot = row.crop_rotation || 0;
                        const nextRot = (curRot + 90) % 360;
                        await processCrop(row.raw_box.x, row.raw_box.y, row.raw_box.w, row.raw_box.h, nextRot, row.id);
                    }
                });
            }

            // Inline edit listeners with Real-Time Adaptive Feedback Loop
            tr.querySelectorAll('.editable-cell').forEach(cell => {
                const field = cell.dataset.field;

                // Enter de luu va bo focus
                cell.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        cell.blur();
                    }
                });

                // Luu gia tri moi khi blur (nguoi dung roi khoi o)
                cell.addEventListener('blur', async () => {
                    const oldVal = row[field];
                    const newVal = cell.textContent.trim();

                    if (oldVal !== newVal) {
                        row[field] = newVal;
                        row.user_corrected = true; // Danh dau user da tu tay sua

                        // Dong bo logic: Neu sua nominal_str thi parse lai float
                        if (field === 'nominal_str') {
                            const parsedNum = parseFloat(newVal.replace(',', '.'));
                            row.nominal = isNaN(parsedNum) ? null : Math.abs(parsedNum);
                        }

                        // Cap nhat lai chuoi callout tong the
                        updateRowCallout(row);

                        // Hien thi badge AI Learned
                        const badge = tr.querySelector('.ai-learned-badge');
                        if (badge) badge.classList.remove('hidden');

                        // Cap nhat text tren o Callout
                        const calloutCell = tr.querySelector('[data-field="full_callout"]');
                        if (calloutCell) calloutCell.textContent = row.full_callout;

                        // =========================================================
                        // REAL-TIME FEEDBACK LOOP: Day ngay quy tac sua len Backend
                        // =========================================================
                        try {
                            const resp = await fetch('/api/feedback/submit', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                    raw_text: row.raw_text,
                                    corrected: {
                                        qty: row.qty || '',
                                        prefix: row.prefix || '',
                                        nominal: row.nominal,
                                        nominal_str: row.nominal_str,
                                        upper_tol: row.upper_tol === '-' ? '' : row.upper_tol,
                                        lower_tol: row.lower_tol === '-' ? '' : row.lower_tol,
                                        tol_type: 'user_defined',
                                        full_callout: row.full_callout
                                    }
                                })
                            });
                            if (resp.ok) {
                                showToast(`💡 AI đã ghi nhớ quy tắc: "${row.raw_text.replace(/\n/g, ' ')}" ➔ ${row.full_callout}`, 'adaptive');
                                updateAdaptiveCount();
                            }
                        } catch (err) {
                            console.log('Loi gui feedback thich ung:', err);
                        }
                    }
                });
            });

            // Delete row
            tr.querySelector('.delete-btn').addEventListener('click', (e) => {
                e.stopPropagation();
                state.rows.splice(originalIdx, 1);
                if (state.selectedRowId === row.id) {
                    state.selectedRowId = null;
                }
                renderTable();
                render();
            });

            // Nhấp vào dòng để Chọn Box xanh tương ứng trên Canvas
            tr.dataset.rowId = row.id;
            if (state.selectedRowId === row.id) {
                tr.classList.add('bg-cyan-950/50', 'border-l-4', 'border-l-cyan-400');
            }
            tr.addEventListener('click', (e) => {
                // Nếu bấm vào input edit hoặc button con thì không trigger chọn
                if (e.target.isContentEditable || e.target.closest('button') || e.target.tagName === 'INPUT') {
                    return;
                }
                if (state.selectedRowId === row.id) {
                    state.selectedRowId = null;
                    unhighlightTableRows();
                } else {
                    state.selectedRowId = row.id;
                    highlightTableRow(row.id);
                }
                render();
            });

            resultsTableBody.appendChild(tr);
        });

        if (query) {
            itemCountBadge.textContent = `${displayCount}/${state.rows.length} mục`;
        }

        // Tự động cuộn đến vị trí kết quả mới nhất
        if (autoScroll && tableScrollContainer) {
            setTimeout(() => {
                if (state.sortOrder === 'desc') {
                    // Khi mới nhất ở trên đầu: Cuộn mượt lên đỉnh bảng
                    tableScrollContainer.scrollTo({
                        top: 0,
                        behavior: 'smooth'
                    });
                } else {
                    // Khi mới nhất ở cuối: Cuộn mượt xuống đáy bảng
                    tableScrollContainer.scrollTo({
                        top: tableScrollContainer.scrollHeight,
                        behavior: 'smooth'
                    });
                }
            }, 60);
        }
    }

    // Lắng nghe sự kiện tìm kiếm / lọc bảng
    if (tableSearchInput) {
        tableSearchInput.addEventListener('input', () => {
            renderTable(false);
        });
    }

    // Helper: Đồng bộ highlight bảng khi chọn box trên canvas
    function highlightTableRow(rowId) {
        if (!resultsTableBody) return;
        resultsTableBody.querySelectorAll('tr').forEach(tr => {
            if (parseInt(tr.dataset.rowId) === rowId) {
                tr.classList.add('bg-cyan-950/40', 'border-l-4', 'border-l-cyan-400');
                tr.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            } else {
                tr.classList.remove('bg-cyan-950/40', 'border-l-4', 'border-l-cyan-400');
            }
        });
    }

    function unhighlightTableRows() {
        if (!resultsTableBody) return;
        resultsTableBody.querySelectorAll('tr').forEach(tr => {
            tr.classList.remove('bg-cyan-950/40', 'border-l-4', 'border-l-cyan-400');
        });
    }

    function updateRowCallout(row) {
        // 1. Nominal luon luon duong, khong co dau am
        if (row.nominal_str) {
            row.nominal_str = row.nominal_str.replace(/^[-+]+/, '');
        }
        if (row.nominal !== null && !isNaN(row.nominal)) {
            row.nominal = Math.abs(row.nominal);
        }

        // 2. Dung sai tren / duoi luon co dau dang truoc (+ hoac - hoac 0)
        if (row.upper_tol && row.upper_tol !== '0' && !row.upper_tol.startsWith('+') && !row.upper_tol.startsWith('-')) {
            row.upper_tol = '+' + row.upper_tol;
        }
        if (row.lower_tol && row.lower_tol !== '0' && !row.lower_tol.startsWith('-') && !row.lower_tol.startsWith('+')) {
            row.lower_tol = '-' + row.lower_tol;
        }

        const parts = [];
        if (row.qty) parts.push(row.qty);
        if (row.prefix) parts.push(row.prefix);
        parts.push(row.nominal_str);
        if (row.upper_tol || row.lower_tol) {
            if (row.upper_tol === (row.lower_tol || '').replace('-', '+')) {
                parts.push(`±${row.upper_tol.replace('+', '')}`);
            } else {
                parts.push(`${row.upper_tol || '0'}/${row.lower_tol || '0'}`);
            }
        }
        row.full_callout = parts.join(' ');
    }

    previewModal.addEventListener('click', () => {
        previewModal.classList.add('hidden');
    });

    // Scroll to Top Button
    if (scrollToTopBtn && tableScrollContainer) {
        scrollToTopBtn.addEventListener('click', () => {
            tableScrollContainer.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
    }

    // Toggle Sort Order: Newest at Top vs Oldest at Top
    if (sortOrderBtn) {
        sortOrderBtn.addEventListener('click', () => {
            state.sortOrder = (state.sortOrder === 'desc') ? 'asc' : 'desc';
            if (state.sortOrder === 'desc') {
                if (sortOrderIcon) sortOrderIcon.className = 'fa-solid fa-arrow-down-9-1 text-cyan-400 text-xs';
                if (sortOrderText) sortOrderText.textContent = 'Mới nhất';
                sortOrderBtn.title = 'Đang sắp xếp: Mới nhất ở trên đầu. Nhấp để chuyển sang cũ nhất ở trên';
                showToast('Đã chuyển sang: Kích thước mới nhất ở trên đầu', 'info');
            } else {
                if (sortOrderIcon) sortOrderIcon.className = 'fa-solid fa-arrow-up-1-9 text-amber-400 text-xs';
                if (sortOrderText) sortOrderText.textContent = 'Cũ nhất';
                sortOrderBtn.title = 'Đang sắp xếp: Cũ nhất ở trên đầu. Nhấp để chuyển sang mới nhất ở trên';
                showToast('Đã chuyển sang: Kích thước từ đầu bản vẽ (1 ➔ N)', 'info');
            }
            renderTable(true);
        });
    }

    clearAllBtn.addEventListener('click', () => {
        if (state.rows.length === 0) return;
        if (confirm('Bạn có chắc muốn xóa toàn bộ danh sách kích thước đã quét?')) {
            state.rows = [];
            renderTable();
            render();
        }
    });

    // Helper: Mở Unified Settings Modal tại tab chỉ định
    function openUnifiedSettings(targetTab = 'tab-ai-vision') {
        if (!unifiedSettingsModal) return;
        
        // Kích hoạt tab tương ứng
        settingsTabBtns.forEach(btn => {
            if (btn.dataset.tab === targetTab) {
                btn.classList.add('active', 'border-blue-500', 'text-blue-400', 'bg-blue-500/10');
                btn.classList.remove('border-transparent', 'text-slate-400');
            } else {
                btn.classList.remove('active', 'border-blue-500', 'text-blue-400', 'bg-blue-500/10');
                btn.classList.add('border-transparent', 'text-slate-400');
            }
        });

        // Hiển thị panel tương ứng
        document.querySelectorAll('.tab-pane').forEach(pane => {
            if (pane.id === targetTab) {
                pane.classList.remove('hidden');
            } else {
                pane.classList.add('hidden');
            }
        });

        // Đồng bộ trạng thái checkbox hiển thị tọa độ & tùy chọn Bubble
        if (showCoordsCheckbox) {
            showCoordsCheckbox.checked = state.showCoordinates;
        }
        const radio = document.querySelector(`input[name="badgeStyleRadio"][value="${state.badgeStyle}"]`);
        if (radio) radio.checked = true;
        if (bubblePositionSelect) bubblePositionSelect.value = state.bubblePosition;
        if (bubbleColorSelect) bubbleColorSelect.value = state.bubbleColor;
        if (bubbleOptionsContainer) {
            bubbleOptionsContainer.style.display = (state.badgeStyle === 'bubble') ? 'grid' : 'none';
        }

        // Nạp dữ liệu cần thiết cho tab
        if (targetTab === 'tab-ai-vision') {
            checkAiVisionStatus();
        } else if (targetTab === 'tab-adaptive') {
            loadAdaptiveRules();
        }

        unifiedSettingsModal.classList.remove('hidden');
    }

    function closeUnifiedSettings() {
        if (unifiedSettingsModal) {
            unifiedSettingsModal.classList.add('hidden');
        }
    }

    // Tab buttons click
    settingsTabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.dataset.tab;
            openUnifiedSettings(targetTab);
        });
    });

    // Triggers to open Unified Settings
    if (openUnifiedSettingsBtn) {
        openUnifiedSettingsBtn.addEventListener('click', () => openUnifiedSettings('tab-ai-vision'));
    }
    if (footerUsageTrigger) {
        footerUsageTrigger.addEventListener('click', () => openUnifiedSettings('tab-ai-vision'));
    }
    if (footerAiModelTrigger) {
        footerAiModelTrigger.addEventListener('click', () => openUnifiedSettings('tab-ai-vision'));
    }
    if (footerTolRuleSummary) {
        footerTolRuleSummary.addEventListener('click', () => openUnifiedSettings('tab-constraints'));
    }

    if (closeUnifiedSettingsBtn) {
        closeUnifiedSettingsBtn.addEventListener('click', closeUnifiedSettings);
    }
    if (cancelUnifiedSettingsBtn) {
        cancelUnifiedSettingsBtn.addEventListener('click', closeUnifiedSettings);
    }

    // Lưu toàn bộ cấu hình (Dung sai chung + AI Vision) khi nhấn nút Lưu & Áp Dụng
    if (saveAllSettingsBtn) {
        saveAllSettingsBtn.addEventListener('click', async () => {
            // 1. Lưu Dung sai chung
            const selectedMode = document.querySelector('input[name="gcMode"]:checked')?.value || 'decimals';
            state.globalConstraints.mode = selectedMode;

            if (selectedMode === 'decimals') {
                state.globalConstraints.decimals = {
                    0: parseFloat(document.getElementById('dec0')?.value) || 0.2,
                    1: parseFloat(document.getElementById('dec1')?.value) || 0.1,
                    2: parseFloat(document.getElementById('dec2')?.value) || 0.05,
                    3: parseFloat(document.getElementById('dec3')?.value) || 0.01,
                    4: parseFloat(document.getElementById('dec4')?.value) || 0.005,
                    5: parseFloat(document.getElementById('dec5')?.value) || 0.001
                };
                if (globalSummaryBadge) globalSummaryBadge.textContent = 'Thập phân';
                if (footerTolRuleSummary) footerTolRuleSummary.textContent = 'Dung sai: Thập phân';
            } else if (selectedMode === 'fixed') {
                state.globalConstraints.fixed_value = parseFloat(document.getElementById('fixedVal')?.value) || 0.1;
                const fixedTxt = `±${state.globalConstraints.fixed_value}mm`;
                if (globalSummaryBadge) globalSummaryBadge.textContent = fixedTxt;
                if (footerTolRuleSummary) footerTolRuleSummary.textContent = `Dung sai: ${fixedTxt}`;
            } else {
                const iso = document.getElementById('isoLevel')?.value || 'iso2768_m';
                state.globalConstraints.mode = iso;
                const isoTxt = iso.replace('iso2768_', 'ISO-');
                if (globalSummaryBadge) globalSummaryBadge.textContent = isoTxt;
                if (footerTolRuleSummary) footerTolRuleSummary.textContent = `Dung sai: ${isoTxt}`;
            }

            // Lưu cài đặt hiển thị tọa độ X, Y
            if (showCoordsCheckbox) {
                setCoordinatesVisibility(showCoordsCheckbox.checked, true);
            }

            // Lưu cài đặt kiểu hiển thị Bubble / Tag
            const chosenStyle = document.querySelector('input[name="badgeStyleRadio"]:checked')?.value || 'bubble';
            setBadgeStyle(chosenStyle, true);
            if (bubblePositionSelect && bubbleColorSelect) {
                updateBubbleConfig(bubblePositionSelect.value, bubbleColorSelect.value, true);
            }

            // 2. Lưu AI Vision Config
            const key = aiApiKeyInput ? aiApiKeyInput.value.trim() : '';
            const model = aiModelSelect ? aiModelSelect.value : 'gemini-flash-latest';
            const tier = aiBillingTierSelect ? aiBillingTierSelect.value : 'free';
            const customRpd = customRpdInput ? parseInt(customRpdInput.value) || 0 : 0;

            try {
                await fetch('/api/ai-vision/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        api_key: key,
                        model_name: model,
                        billing_tier: tier,
                        custom_rpd_limit: customRpd
                    })
                });
                showToast('✅ Đã lưu cấu hình hệ thống & dung sai thành công!', 'success');
            } catch (err) {
                console.error('Lỗi lưu AI Config:', err);
                showToast('Đã cập nhật dung sai chung!', 'success');
            }

            await checkAiVisionStatus();
            closeUnifiedSettings();
        });
    }

    // Export to Excel
    exportExcelBtn.addEventListener('click', async () => {
        if (state.rows.length === 0) {
            alert('Chưa có dữ liệu nào để xuất!');
            return;
        }

        const baseName = state.filename.replace('.pdf', '');
        const payload = {
            drawing_name: baseName,
            global_constraints_summary: globalSummaryBadge.textContent,
            rows: state.rows
        };

        try {
            const resp = await fetch('/api/export-excel', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (!resp.ok) throw new Error('Lỗi xuất Excel');
            
            const blob = await resp.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${baseName}_Tolerances.xlsx`;
            document.body.appendChild(a);
            a.click();
            a.remove();
        } catch (err) {
            alert('Lỗi: ' + err.message);
        }
    });

    // Export to CSV
    exportCsvBtn.addEventListener('click', async () => {
        if (state.rows.length === 0) return;
        const baseName = state.filename.replace('.pdf', '');
        const payload = {
            drawing_name: baseName,
            rows: state.rows
        };

        try {
            const resp = await fetch('/api/export-csv', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const blob = await resp.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${baseName}_Tolerances.csv`;
            document.body.appendChild(a);
            a.click();
            a.remove();
        } catch (err) {
            alert('Lỗi: ' + err.message);
        }
    });

    // Adaptive Learning Modal Logic
    async function updateAdaptiveCount() {
        try {
            const resp = await fetch('/api/feedback/rules');
            const data = await resp.json();
            const exactCount = Object.keys(data.exact_matches || {}).length;
            const genCount = (data.generalized_rules || []).length;
            const total = exactCount + genCount;
            if (adaptiveCountBadge) {
                adaptiveCountBadge.textContent = `${total} quy tắc`;
            }
        } catch (e) {
            console.log('Error updating adaptive count:', e);
        }
    }

    async function loadAdaptiveRules() {
        if (!exactRulesList || !genRulesList) return;
        try {
            const resp = await fetch('/api/feedback/rules');
            const data = await resp.json();
            
            // 1. Exact Rules List
            exactRulesList.innerHTML = '';
            const exactKeys = Object.keys(data.exact_matches || {});
            if (exactKeys.length === 0) {
                exactRulesList.innerHTML = '<p class="text-slate-500 italic py-1">Chưa có quy tắc 1-shot nào. Hãy sửa bất kỳ kích thước nào trên bảng để AI tự học!</p>';
            } else {
                exactKeys.forEach(key => {
                    const item = data.exact_matches[key];
                    const div = document.createElement('div');
                    div.className = 'flex items-center justify-between bg-slate-900/80 p-2 rounded border border-slate-700/60 font-mono text-[11px]';
                    div.innerHTML = `
                        <div class="flex items-center space-x-2">
                            <span class="text-slate-400 bg-slate-800 px-1.5 py-0.5 rounded border border-slate-700">${item.raw_text.replace(/\n/g, ' ')}</span>
                            <span class="text-amber-400">➔</span>
                            <span class="text-emerald-300 font-bold">${item.full_callout}</span>
                        </div>
                        <button class="text-slate-500 hover:text-red-400 del-rule-btn px-1" title="Xóa quy tắc này"><i class="fa-solid fa-trash-can"></i></button>
                    `;
                    div.querySelector('.del-rule-btn').addEventListener('click', async () => {
                        await fetch(`/api/feedback/rules?key=${encodeURIComponent(key)}&rule_type=exact`, { method: 'DELETE' });
                        showToast(`Đã xóa quy tắc cho "${key}"`, 'adaptive');
                        loadAdaptiveRules();
                        updateAdaptiveCount();
                    });
                    exactRulesList.appendChild(div);
                });
            }

            // 2. Generalized Rules List
            genRulesList.innerHTML = '';
            const genRules = data.generalized_rules || [];
            if (genRules.length === 0) {
                genRulesList.innerHTML = '<p class="text-slate-500 italic py-1">Chưa có quy tắc tổng quát nào.</p>';
            } else {
                genRules.forEach(rule => {
                    const div = document.createElement('div');
                    div.className = 'flex items-center justify-between bg-slate-900/80 p-2 rounded border border-slate-700/60 font-mono text-[11px]';
                    div.innerHTML = `
                        <div>
                            <span class="text-blue-300 font-bold">${rule.name}</span>
                            <div class="text-[10px] text-slate-500 truncate max-w-md">${rule.pattern}</div>
                        </div>
                        <span class="text-[10px] bg-blue-900/40 text-blue-300 px-1.5 py-0.5 rounded border border-blue-700/40 font-mono">Tự động</span>
                    `;
                    genRulesList.appendChild(div);
                });
            }
        } catch (e) {
            console.log('Error loading adaptive rules:', e);
        }
    }

    // =========================================================================
    // AI VISION LOGIC, USAGE PERCENTAGE & AUTO-SCAN
    // =========================================================================
    function updateUsageUI(usage) {
        if (!usage) return;

        const pct = usage.percent_rpd || 0;
        const rpdUsed = usage.rpd_used || 0;
        const rpdLimit = usage.rpd_limit || 1500;
        const rpmUsed = usage.rpm_used || 0;
        const rpmLimit = usage.rpm_limit || 15;
        const tokens = usage.day_tokens || 0;

        // 1. Header Usage Bar
        if (aiUsagePercentText) {
            aiUsagePercentText.textContent = `${pct}%`;
            if (pct >= 90) {
                aiUsagePercentText.className = 'text-red-400 font-bold';
            } else if (pct >= 70) {
                aiUsagePercentText.className = 'text-amber-400 font-bold';
            } else {
                aiUsagePercentText.className = 'text-purple-300 font-semibold';
            }
        }

        if (aiUsageProgressBar) {
            aiUsageProgressBar.style.width = `${Math.min(100, Math.max(2, pct))}%`;
            if (pct >= 90) {
                aiUsageProgressBar.className = 'h-full bg-red-500 rounded-full transition-all duration-500';
            } else if (pct >= 70) {
                aiUsageProgressBar.className = 'h-full bg-amber-500 rounded-full transition-all duration-500';
            } else {
                aiUsageProgressBar.className = 'h-full bg-gradient-to-r from-purple-500 to-indigo-400 rounded-full transition-all duration-500';
            }
        }

        if (aiUsageReqText) {
            aiUsageReqText.textContent = `${rpdUsed}/${rpdLimit}`;
        }

        // 2. Modal Breakdown
        if (aiModalPercentBadge) {
            aiModalPercentBadge.textContent = `${pct}% used`;
        }
        if (aiModalRpdText) {
            aiModalRpdText.textContent = `${rpdUsed} / ${rpdLimit} req`;
        }
        if (aiModalRpdBar) {
            aiModalRpdBar.style.width = `${Math.min(100, pct)}%`;
        }
        if (aiModalRpmText) {
            aiModalRpmText.textContent = `${rpmUsed} / ${rpmLimit} req/phút`;
        }
        if (aiModalRpmBar) {
            const rpmPct = Math.min(100, (rpmUsed / rpmLimit) * 100);
            aiModalRpmBar.style.width = `${rpmPct}%`;
        }
        if (aiModalTokensText) {
            aiModalTokensText.textContent = Number(tokens).toLocaleString();
        }
        if (aiModalCostText) {
            const cost = usage.estimated_cost_usd || 0;
            aiModalCostText.textContent = `($${cost.toFixed(4)})`;
        }

        if (aiModalTierBadge) {
            const isPaid = (usage.billing_tier === 'paid');
            aiModalTierBadge.innerHTML = isPaid
                ? '<i class="fa-solid fa-bolt text-indigo-400"></i><span class="text-indigo-300 font-semibold">Pay-as-you-go</span>'
                : '<i class="fa-solid fa-circle-check text-emerald-400"></i><span class="text-emerald-300">Gói Free Tier</span>';
        }

        // Tier Select & Custom Quota Container sync
        if (aiBillingTierSelect && usage.billing_tier) {
            aiBillingTierSelect.value = usage.billing_tier;
            if (customQuotaContainer) {
                if (usage.billing_tier === 'paid') {
                    customQuotaContainer.classList.remove('hidden');
                } else {
                    customQuotaContainer.classList.add('hidden');
                }
            }
        }
        if (customRpdInput && usage.custom_rpd_limit !== undefined) {
            customRpdInput.value = usage.custom_rpd_limit > 0 ? usage.custom_rpd_limit : '';
        }
    }

    // Toggle custom quota input when tier changes
    if (aiBillingTierSelect) {
        aiBillingTierSelect.addEventListener('change', () => {
            if (customQuotaContainer) {
                if (aiBillingTierSelect.value === 'paid') {
                    customQuotaContainer.classList.remove('hidden');
                } else {
                    customQuotaContainer.classList.add('hidden');
                }
            }
        });
    }

    async function checkAiVisionStatus() {
        try {
            const resp = await fetch('/api/ai-vision/status');
            const data = await resp.json();
            const isReady = (data.configured && data.status === 'ready');
            const modelDisplay = data.model 
                ? (data.model.includes('pro') ? 'Gemini Pro' : data.model.includes('flash-lite') ? 'Flash-Lite' : 'Gemini Flash') 
                : 'Gemini Flash';

            if (isReady) {
                if (aiStatusDot) aiStatusDot.className = 'w-2.5 h-2.5 rounded-full bg-emerald-400 shrink-0';
                if (aiStatusDetail) aiStatusDetail.textContent = `Sẵn sàng hoạt động (${modelDisplay})`;
                if (data.model && aiModelSelect) aiModelSelect.value = data.model;
                if (data.billing_tier && aiBillingTierSelect) aiBillingTierSelect.value = data.billing_tier;
                if (data.masked_key && aiApiKeyInput) {
                    if (!aiApiKeyInput.value || aiApiKeyInput.value.includes('•••')) {
                        aiApiKeyInput.value = data.masked_key;
                        aiApiKeyInput.dataset.hasSavedKey = 'true';
                    }
                }
                if (footerAiDot) footerAiDot.className = 'w-2 h-2 rounded-full bg-emerald-400';
                if (footerAiModelText) footerAiModelText.textContent = modelDisplay;
                if (headerSettingsDot) headerSettingsDot.className = 'w-2 h-2 rounded-full bg-emerald-400 ml-0.5';
            } else {
                if (aiStatusDot) aiStatusDot.className = 'w-2.5 h-2.5 rounded-full bg-amber-400 shrink-0';
                if (aiStatusDetail) aiStatusDetail.textContent = data.message || 'Chưa cấu hình API Key';
                if (aiApiKeyInput) {
                    delete aiApiKeyInput.dataset.hasSavedKey;
                    if (aiApiKeyInput.value.includes('•••')) aiApiKeyInput.value = '';
                }
                if (footerAiDot) footerAiDot.className = 'w-2 h-2 rounded-full bg-amber-400';
                if (footerAiModelText) footerAiModelText.textContent = 'Chưa cài API Key';
                if (headerSettingsDot) headerSettingsDot.className = 'w-2 h-2 rounded-full bg-amber-400 ml-0.5';
            }

            // Update usage bar
            if (data.usage) {
                updateUsageUI(data.usage);
            }
        } catch (e) {
            console.error('Error checking AI status:', e);
        }
    }

    if (toggleAiKeyVisBtn && aiApiKeyInput) {
        toggleAiKeyVisBtn.addEventListener('click', () => {
            if (aiApiKeyInput.type === 'password') {
                aiApiKeyInput.type = 'text';
                toggleAiKeyVisBtn.innerHTML = '<i class="fa-solid fa-eye-slash text-xs"></i>';
            } else {
                aiApiKeyInput.type = 'password';
                toggleAiKeyVisBtn.innerHTML = '<i class="fa-solid fa-eye text-xs"></i>';
            }
        });
    }

    if (testAiKeyBtn) {
        testAiKeyBtn.addEventListener('click', async () => {
            const key = aiApiKeyInput.value.trim();
            const model = aiModelSelect.value;
            const tier = aiBillingTierSelect ? aiBillingTierSelect.value : 'free';
            const customRpd = customRpdInput ? parseInt(customRpdInput.value) || 0 : 0;

            if (!key) {
                alert('Vui lòng nhập API Key trước khi kiểm tra!');
                return;
            }

            testAiKeyBtn.innerHTML = '<i class="fa-solid fa-spinner animate-spin"></i> Đang test...';
            testAiKeyBtn.disabled = true;

            try {
                const resp = await fetch('/api/ai-vision/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        api_key: key,
                        model_name: model,
                        billing_tier: tier,
                        custom_rpd_limit: customRpd
                    })
                });
                const res = await resp.json();
                if (res.status && res.status.configured) {
                    showToast('✅ Kết nối Google Gemini Vision thành công!', 'success');
                    checkAiVisionStatus();
                } else {
                    alert('Lỗi: ' + (res.status?.message || 'Không thể kết nối với API Key này'));
                    checkAiVisionStatus();
                }
            } catch (err) {
                alert('Lỗi kiểm tra: ' + err.message);
            } finally {
                testAiKeyBtn.innerHTML = '<i class="fa-solid fa-plug"></i> <span>Kiểm tra</span>';
                testAiKeyBtn.disabled = false;
            }
        });
    }

    if (clearAiKeyBtn) {
        clearAiKeyBtn.addEventListener('click', async () => {
            if (confirm('Bạn có chắc muốn gỡ bỏ API Key này khỏi hệ thống không?')) {
                try {
                    await fetch('/api/ai-vision/config', { method: 'DELETE' });
                    if (aiApiKeyInput) aiApiKeyInput.value = '';
                    showToast('Đã gỡ bỏ API Key thành công!', 'adaptive');
                    await checkAiVisionStatus();
                } catch (e) {
                    alert('Lỗi gỡ API key: ' + e.message);
                }
            }
        });
    }

    // AI Vision Auto-Scan entire drawing page
    if (aiAutoScanBtn) {
        aiAutoScanBtn.addEventListener('click', async () => {
            if (!state.fileId) {
                alert('Vui lòng mở hoặc tải bản vẽ PDF trước khi dùng AI Auto-Scan!');
                return;
            }

            loadingText.textContent = '🤖 AI Vision đang quét và định vị các kích thước trên bản vẽ...';
            loadingOverlay.classList.remove('hidden');

            try {
                const resp = await fetch('/api/ai-vision/auto-detect', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        file_id: state.fileId,
                        page_num: state.currentPage,
                        page_rotation: state.pageRotation
                    })
                });
                const data = await resp.json();
                if (!resp.ok || !data.success) {
                    throw new Error(data.error || 'Lỗi khi AI Auto-Detect');
                }

                const dims = data.dimensions || [];
                if (dims.length === 0) {
                    showToast('AI Vision không tìm thấy kích thước nào rõ ràng trên trang này', 'info');
                    return;
                }

                showToast(`🤖 AI Vision đã phát hiện ${dims.length} kích thước! Đang bóc tách chi tiết...`, 'info');

                let addedCount = 0;
                let completedCount = 0;

                // Hàm bóc tách 1 dimension
                const processSingleDim = async (d) => {
                    try {
                        const cropResp = await fetch('/api/crop-ocr', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                file_id: state.fileId,
                                page_num: state.currentPage,
                                crop_box: d.crop_box,
                                global_constraints: state.globalConstraints,
                                page_rotation: state.pageRotation,
                                crop_rotation: 0
                            })
                        });
                        const cropData = await cropResp.json();
                        if (cropResp.ok && (cropData.nominal_str || cropData.raw_text)) {
                            const newBox = d.box || cropData.box;
                            // Kiểm tra xem có bị trùng/chồng đè với box đã tồn tại trên trang không
                            const existingRow = state.rows.find(r => 
                                r.page === state.currentPage && 
                                r.raw_box && 
                                calculateBoxOverlap(newBox, r.raw_box) > 0.5
                            );

                            const rowPayload = {
                                thumbnail: cropData.thumbnail,
                                qty: cropData.qty || '',
                                prefix: cropData.prefix || '',
                                nominal: cropData.nominal,
                                nominal_str: cropData.nominal_str || (cropData.nominal !== null ? String(cropData.nominal) : ''),
                                upper_tol: cropData.upper_tol || '',
                                lower_tol: cropData.lower_tol || '',
                                tol_type: cropData.tol_type || 'local',
                                full_callout: cropData.full_callout || cropData.raw_text || d.label,
                                raw_text: cropData.raw_text || d.label || '',
                                raw_box: d.box,
                                box: cropData.box || d.box,
                                norm_box: d.crop_box,
                                crop_rotation: 0,
                                is_auto_detected: true
                            };

                            if (existingRow) {
                                Object.assign(existingRow, rowPayload);
                            } else {
                                const newRow = {
                                    id: state.rows.length + 1,
                                    page: state.currentPage,
                                    ...rowPayload
                                };
                                state.rows.push(newRow);
                                addedCount++;
                            }
                        }
                    } catch (e) {
                        console.error('Lỗi bóc tách ô crop:', e);
                    } finally {
                        completedCount++;
                        loadingText.textContent = `🤖 Đang bóc tách chi tiết: ${completedCount}/${dims.length} kích thước...`;
                    }
                };

                // Chạy đồng thời theo lô 6 request song song để tăng tốc độ gấp 5-6 lần
                const CONCURRENCY_LIMIT = 6;
                for (let i = 0; i < dims.length; i += CONCURRENCY_LIMIT) {
                    const batch = dims.slice(i, i + CONCURRENCY_LIMIT);
                    await Promise.all(batch.map(d => processSingleDim(d)));
                    // Cập nhật canvas và bảng định kỳ theo từng batch để người dùng nhìn thấy bong bóng xuất hiện dần
                    renderTable(true, state.rows.length - 1);
                    render();
                }

                showToast(`🎉 AI Auto-Scan hoàn tất: Đã bóc tách thành công ${addedCount} kích thước!`, 'success');

            } catch (err) {
                alert('Lỗi AI Auto-Scan: ' + err.message);
            } finally {
                loadingOverlay.classList.add('hidden');
                loadingText.textContent = 'Đang quét OCR & bóc tách dung sai...';
                checkAiVisionStatus();
            }
        });
    }

    // Init AI status on startup
    checkAiVisionStatus();

    // Init adaptive count on startup
    updateAdaptiveCount();

    // Tu dong tai ban ve mau tren he thong neu chua co ban ve nao
    setTimeout(async () => {
        if (!state.fileId) {
            try {
                const resp = await fetch('/api/load-sample');
                const data = await resp.json();
                if (data.success) {
                    state.fileId = data.file_id;
                    state.filename = data.filename;
                    state.pageCount = data.page_count;
                    state.currentPage = 0;
                    await loadPageImage(0);
                    emptyState.classList.add('hidden');
                    docName.textContent = data.filename;
                    pageNavContainer.classList.remove('hidden');
                    updatePageIndicator();
                    exportExcelBtn.disabled = false;
                    exportCsvBtn.disabled = false;
                }
            } catch (e) {
                console.log('Auto-load:', e);
            }
        }
    }, 400);
});
