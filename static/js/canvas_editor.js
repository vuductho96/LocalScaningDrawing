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
        
        // Rotation (0, 90, 180, 270)
        pageRotation: 0,
        cropRotation: 0,
        
        // Global Constraints Settings (0, 0.0, 0.00, 0.000, 0.0000, 0.00000)
        globalConstraints: {
            mode: 'decimals',
            fixed_value: 0.1,
            decimals: { 0: 0.2, 1: 0.1, 2: 0.05, 3: 0.01, 4: 0.005, 5: 0.001 }
        }
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

    const rotatePdfBtn = document.getElementById('rotatePdfBtn');
    const pageRotationText = document.getElementById('pageRotationText');
    const rotateCropBtn = document.getElementById('rotateCropBtn');
    const cropRotationText = document.getElementById('cropRotationText');
    
    const pdfFileInput = document.getElementById('pdfFileInput');
    const pdfFileInput2 = document.getElementById('pdfFileInput2');
    const exportExcelBtn = document.getElementById('exportExcelBtn');
    const exportCsvBtn = document.getElementById('exportCsvBtn');
    const clearAllBtn = document.getElementById('clearAllBtn');
    
    const constraintsModal = document.getElementById('constraintsModal');
    const openConstraintsBtn = document.getElementById('openConstraintsBtn');
    const closeConstraintsBtn = document.getElementById('closeConstraintsBtn');
    const cancelConstraintsBtn = document.getElementById('cancelConstraintsBtn');
    const saveConstraintsBtn = document.getElementById('saveConstraintsBtn');
    const globalSummaryBadge = document.getElementById('globalSummaryBadge');

    const previewModal = document.getElementById('previewModal');
    const previewImg = document.getElementById('previewImg');

    const adaptiveModal = document.getElementById('adaptiveModal');
    const openAdaptiveBtn = document.getElementById('openAdaptiveBtn');
    const closeAdaptiveBtn = document.getElementById('closeAdaptiveBtn');
    const closeAdaptiveBtn2 = document.getElementById('closeAdaptiveBtn2');
    const adaptiveCountBadge = document.getElementById('adaptiveCountBadge');
    const exactRulesList = document.getElementById('exactRulesList');
    const genRulesList = document.getElementById('genRulesList');
    const toastContainer = document.getElementById('toastContainer');

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
                ctx.fillStyle = 'rgba(59, 130, 246, 0.15)';
                ctx.strokeStyle = '#3b82f6';
                ctx.lineWidth = 2 / state.scale;
                ctx.fillRect(r.raw_box.x, r.raw_box.y, r.raw_box.w, r.raw_box.h);
                ctx.strokeRect(r.raw_box.x, r.raw_box.y, r.raw_box.w, r.raw_box.h);

                // Ve nhan so thu tu va toa do X, Y
                const labelText = `#${r.id} (${Math.round(r.raw_box.x)}, ${Math.round(r.raw_box.y)})`;
                ctx.font = `bold ${Math.max(10, 11 / state.scale)}px monospace`;
                const pad = 4 / state.scale;
                const textWidth = ctx.measureText(labelText).width;

                ctx.fillStyle = '#1e3a8a';
                ctx.fillRect(r.raw_box.x, r.raw_box.y - 18 / state.scale, textWidth + pad * 2, 18 / state.scale);
                ctx.strokeStyle = '#3b82f6';
                ctx.strokeRect(r.raw_box.x, r.raw_box.y - 18 / state.scale, textWidth + pad * 2, 18 / state.scale);
                ctx.fillStyle = '#67e8f9';
                ctx.fillText(labelText, r.raw_box.x + pad, r.raw_box.y - 5 / state.scale);
            }
        });

        // 3. Ve o crop dang keo (Active selection box kem toa do Live)
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

            // Nhan toa do thuc thoi
            const liveCoord = `X:${Math.round(x)} Y:${Math.round(y)} (${Math.round(w)}x${Math.round(h)})`;
            ctx.font = `bold ${Math.max(10, 11 / state.scale)}px monospace`;
            const liveWidth = ctx.measureText(liveCoord).width;
            ctx.fillStyle = 'rgba(15, 23, 42, 0.9)';
            ctx.fillRect(x, y - 20 / state.scale, liveWidth + 8 / state.scale, 18 / state.scale);
            ctx.fillStyle = '#22d3ee';
            ctx.fillText(liveCoord, x + 4 / state.scale, y - 6 / state.scale);
        }

        ctx.restore();
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

        if (e.key === 'Escape' && state.isPanModeActive) {
            setPanMode(false);
            return;
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

    // Canvas Mouse Events
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

        // Chuột trái (button 0) ở chế độ bình thường -> Kéo ô Crop selection
        if (e.button === 0) {
            const pt = screenToImage(e.clientX, e.clientY);
            state.isLeftDown = true;
            state.startX = pt.x;
            state.startY = pt.y;
            state.currentX = pt.x;
            state.currentY = pt.y;
            render();
        }
    });

    window.addEventListener('mousemove', (e) => {
        if (state.isPanning) {
            state.panX = e.clientX - state.panStartX;
            state.panY = e.clientY - state.panStartY;
            render();
            return;
        }

        if (state.isLeftDown) {
            const pt = screenToImage(e.clientX, e.clientY);
            state.currentX = pt.x;
            state.currentY = pt.y;
            render();
        }
    });

    window.addEventListener('mouseup', async (e) => {
        if (state.isPanning) {
            state.isPanning = false;
            viewport.style.cursor = (state.isPanModeActive || isCtrlPressed || isSpacePressed || e.ctrlKey) ? 'grab' : 'crosshair';
            return;
        }

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
                await processCrop(x0, y0, w, h);
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

    // Rotate PDF Button (Xoay trang PDF 90 do)
    if (rotatePdfBtn) {
        rotatePdfBtn.addEventListener('click', async () => {
            if (!state.fileId) return;
            state.pageRotation = (state.pageRotation + 90) % 360;
            if (pageRotationText) pageRotationText.textContent = `${state.pageRotation}°`;
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
            if (cropRotationText) cropRotationText.textContent = `${state.cropRotation}°`;
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
            if (pageRotationText) pageRotationText.textContent = '0°';
            if (cropRotationText) cropRotationText.textContent = '0°';
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
                    showToast(`Đã xoay ${cropRot}° và quét lại mục #${targetRowId}`, 'success');
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
            }

            renderTable();
            render(); // Ve them o crop overlay

        } catch (err) {
            alert('Lỗi: ' + err.message);
        } finally {
            loadingOverlay.classList.add('hidden');
        }
    }

    // Render Table Body
    function renderTable() {
        resultsTableBody.innerHTML = '';
        itemCountBadge.textContent = `${state.rows.length} mục`;

        if (state.rows.length === 0) {
            tableEmptyState.classList.remove('hidden');
            return;
        }
        tableEmptyState.classList.add('hidden');

        state.rows.forEach((row, idx) => {
            const tr = document.createElement('tr');
            tr.className = 'hover:bg-slate-800/50 transition group border-b border-slate-800/40';

            const isGlobal = row.tol_type === 'global';
            const isLearned = row.source && row.source.startsWith('adaptive');
            const isUserCorrected = row.user_corrected;

            let badgeClass = 'bg-blue-900/50 text-blue-300 border-blue-700/60';
            let badgeText = 'Local';
            if (isLearned || isUserCorrected) {
                badgeClass = 'bg-amber-900/60 text-amber-300 border-amber-600/70 shadow-sm';
                badgeText = 'AI Đã học';
            } else if (row.tol_type === 'angle') {
                badgeClass = 'bg-purple-900/50 text-purple-300 border-purple-700/60';
                badgeText = 'Góc độ';
            } else if (isGlobal) {
                badgeClass = 'bg-emerald-900/50 text-emerald-300 border-emerald-700/60';
                badgeText = 'Global';
            }

            const safeThumb = (row.thumbnail && row.thumbnail !== 'undefined') 
                ? row.thumbnail 
                : 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="48" height="28" fill="%23334155"><rect width="48" height="28" fill="%231e293b"/><text x="24" y="17" fill="%2364748b" font-size="9" text-anchor="middle" font-family="sans-serif">Crop</text></svg>';

            const box = row.box || row.raw_box || { x: 0, y: 0, w: 0, h: 0 };
            const coordStr = `X:${Math.round(box.x)} Y:${Math.round(box.y)}`;
            const coordTooltip = `Tọa độ Crop:\nX=${Math.round(box.x)}, Y=${Math.round(box.y)}, W=${Math.round(box.w)}, H=${Math.round(box.h)}\nTrang: ${row.page !== undefined ? row.page + 1 : 1}\nNhấp để sao chép tọa độ JSON cho AI/Debug`;

            tr.innerHTML = `
                <td class="py-2 px-2 text-center text-slate-500 font-mono text-[11px]">${idx + 1}</td>
                <td class="py-2 px-2 text-center">
                    <img src="${safeThumb}" class="w-12 h-7 object-contain bg-white rounded border border-slate-700 cursor-pointer hover:scale-125 transition origin-left shadow mx-auto" data-img="${safeThumb}">
                    <button class="copy-coords-btn text-[9px] font-mono text-cyan-400/90 bg-slate-900/90 px-1 py-0.5 rounded mt-1 border border-slate-700/80 hover:border-cyan-400 hover:text-cyan-200 hover:bg-slate-800 transition block mx-auto text-center cursor-pointer shadow-sm" title="${coordTooltip}">
                        <i class="fa-solid fa-crosshairs text-[8px] text-cyan-500 mr-0.5"></i>${coordStr}
                    </button>
                </td>
                <td class="py-2 px-2">
                    <span class="text-[11px] font-mono text-slate-400 bg-slate-800/80 px-1.5 py-0.5 rounded border border-slate-700/60 break-all select-all block max-w-[130px] truncate" title="${row.raw_text.replace(/"/g, '&quot;')}">${row.raw_text.replace(/\n/g, ' ') || '-'}</span>
                </td>
                <td class="py-2 px-2">
                    <div class="flex items-center space-x-1">
                        ${row.prefix ? `<span class="text-amber-400 font-bold font-mono">${row.prefix}</span>` : ''}
                        <span class="editable-cell font-mono font-semibold text-slate-100 px-1 py-0.5" contenteditable="true" data-field="nominal_str">${row.nominal_str}</span>
                        ${row.qty ? `<span class="text-xs text-slate-400">(${row.qty})</span>` : ''}
                    </div>
                </td>
                <td class="py-2 px-2 text-center">
                    <div class="inline-flex flex-col text-[11px] font-mono leading-tight">
                        <span class="editable-cell text-blue-300 px-1" contenteditable="true" data-field="upper_tol">${row.upper_tol || '-'}</span>
                        <span class="editable-cell text-red-300 px-1" contenteditable="true" data-field="lower_tol">${row.lower_tol || '-'}</span>
                    </div>
                </td>
                <td class="py-2 px-2">
                    <span class="editable-cell font-mono font-bold text-cyan-300 text-[11px] px-1 py-0.5 block truncate max-w-[140px]" contenteditable="true" data-field="full_callout" title="${(row.full_callout || '').replace(/"/g, '&quot;')}">${row.full_callout || '-'}</span>
                </td>
                <td class="py-2 px-2 text-center">
                    <span class="text-[10px] px-1.5 py-0.5 rounded border font-mono ${badgeClass}">${badgeText}</span>
                </td>
                <td class="py-2 px-2 text-center whitespace-nowrap">
                    <button class="rotate-row-btn text-slate-400 hover:text-cyan-400 p-1 mr-1 transition" title="Xoay ảnh 90° và quét lại OCR (Dành cho kích thước dọc)"><i class="fa-solid fa-arrow-rotate-right"></i></button>
                    <button class="text-slate-500 hover:text-red-400 delete-btn p-1 transition" title="Xóa dòng"><i class="fa-solid fa-xmark"></i></button>
                </td>
            `;

            // Thumbnail click preview
            const thumbImg = tr.querySelector('img');
            thumbImg.addEventListener('click', () => {
                previewImg.src = row.thumbnail;
                previewModal.classList.remove('hidden');
            });

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

            // Copy coordinates JSON for AI / debug
            const copyCoordBtn = tr.querySelector('.copy-coords-btn');
            if (copyCoordBtn) {
                copyCoordBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const b = row.box || row.raw_box || { x: 0, y: 0, w: 0, h: 0 };
                    const coordJson = JSON.stringify({
                        id: row.id,
                        page: row.page ?? state.currentPage,
                        box: b,
                        norm_box: row.norm_box || {
                            x: b.x / state.pageWidth,
                            y: b.y / state.pageHeight,
                            width: b.w / state.pageWidth,
                            height: b.h / state.pageHeight
                        }
                    }, null, 2);
                    navigator.clipboard.writeText(coordJson).then(() => {
                        showToast(`📋 Đã sao chép tọa độ mục #${idx + 1} (${coordStr}) vào Clipboard`, 'success');
                    }).catch(() => {
                        showToast(`Tọa độ #${idx + 1}: ${coordStr}`, 'info');
                    });
                });
            }

            // Inline edit listeners with Real-Time Adaptive Feedback Loop
            tr.querySelectorAll('.editable-cell').forEach(cell => {
                let initialVal = cell.innerText.trim();
                cell.addEventListener('focus', (e) => {
                    initialVal = e.target.innerText.trim();
                });

                cell.addEventListener('blur', async (e) => {
                    const field = e.target.dataset.field;
                    const newVal = e.target.innerText.trim();
                    if (newVal === initialVal) return; // Khong thay doi

                    row[field] = newVal;
                    if (field === 'nominal_str') {
                        const parsedNum = parseFloat(row[field]);
                        if (!isNaN(parsedNum)) row.nominal = parsedNum;
                    }
                    if (field !== 'full_callout') {
                        updateRowCallout(row);
                    }

                    row.user_corrected = true;
                    // Cap nhat badge "AI Da hoc" ngay lap tuc
                    const badgeSpan = tr.querySelector('td:nth-last-child(2) span');
                    if (badgeSpan) {
                        badgeSpan.className = 'text-[10px] px-1.5 py-0.5 rounded border font-mono bg-amber-900/60 text-amber-300 border-amber-600/70 shadow-sm';
                        badgeSpan.textContent = 'AI Đã học';
                    }

                    // Gui phan hoi len server de hoc thich ung 1-Shot
                    if (row.raw_text) {
                        try {
                            const resp = await fetch('/api/feedback/correct', {
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
                                        suffix: row.suffix || '',
                                        full_callout: row.full_callout
                                    }
                                })
                            });
                            if (resp.ok) {
                                showToast(`💡 AI đã ghi nhớ: "${row.raw_text.replace(/\n/g, ' ')}" ➔ ${row.full_callout}`, 'adaptive');
                                updateAdaptiveCount();
                            }
                        } catch (err) {
                            console.log('Loi gui feedback thich ung:', err);
                        }
                    }
                });
            });

            // Delete row
            tr.querySelector('.delete-btn').addEventListener('click', () => {
                state.rows.splice(idx, 1);
                renderTable();
                render();
            });

            resultsTableBody.appendChild(tr);
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

    clearAllBtn.addEventListener('click', () => {
        if (state.rows.length === 0) return;
        if (confirm('Bạn có chắc muốn xóa toàn bộ danh sách kích thước đã quét?')) {
            state.rows = [];
            renderTable();
            render();
        }
    });

    // Global Constraints Modal
    openConstraintsBtn.addEventListener('click', () => {
        constraintsModal.classList.remove('hidden');
    });
    closeConstraintsBtn.addEventListener('click', () => constraintsModal.classList.add('hidden'));
    cancelConstraintsBtn.addEventListener('click', () => constraintsModal.classList.add('hidden'));

    saveConstraintsBtn.addEventListener('click', () => {
        const selectedMode = document.querySelector('input[name="gcMode"]:checked').value;
        state.globalConstraints.mode = selectedMode;

        if (selectedMode === 'decimals') {
            state.globalConstraints.decimals = {
                0: parseFloat(document.getElementById('dec0').value) || 0.2,
                1: parseFloat(document.getElementById('dec1').value) || 0.1,
                2: parseFloat(document.getElementById('dec2').value) || 0.05,
                3: parseFloat(document.getElementById('dec3').value) || 0.01,
                4: parseFloat(document.getElementById('dec4').value) || 0.005,
                5: parseFloat(document.getElementById('dec5').value) || 0.001
            };
            globalSummaryBadge.textContent = 'Thập phân';
        } else if (selectedMode === 'fixed') {
            state.globalConstraints.fixed_value = parseFloat(document.getElementById('fixedVal').value) || 0.1;
            globalSummaryBadge.textContent = `±${state.globalConstraints.fixed_value}mm`;
        } else {
            const iso = document.getElementById('isoLevel').value;
            state.globalConstraints.mode = iso;
            globalSummaryBadge.textContent = iso.replace('iso2768_', 'ISO-');
        }

        constraintsModal.classList.add('hidden');
    });

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

    if (openAdaptiveBtn) {
        openAdaptiveBtn.addEventListener('click', () => {
            loadAdaptiveRules();
            adaptiveModal.classList.remove('hidden');
        });
    }
    if (closeAdaptiveBtn) closeAdaptiveBtn.addEventListener('click', () => adaptiveModal.classList.add('hidden'));
    if (closeAdaptiveBtn2) closeAdaptiveBtn2.addEventListener('click', () => adaptiveModal.classList.add('hidden'));

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
