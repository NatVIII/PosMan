/**
 * PDF Preview with Bleed Overlay for Poster Upload
 * Uses PDF.js for rendering and Canvas for overlay guides.
 */

(function() {
    'use strict';

    // PDF.js worker
    pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

    // State
    let pdfDoc = null;
    let currentPageNum = 1;
    let currentPage = null;
    let currentPageWidthPoints = 0;
    let currentPageHeightPoints = 0;
    let canvas = null;
    let overlay = null;
    let ctx = null;
    let overlayCtx = null;
     let renderTask = null;
     let previewScale = 1.0;
     let paperScale = 1.0;
      let rotationAngle = 0; // 0, 90, 180, 270
      let lastPosterRect = null; // {x, y, width, height} in canvas pixels
      let isImageMode = false;
      let currentImage = null;

    // DOM Elements
    const pdfFileInput = document.getElementById('pdf_file');
    const pageSelect = document.getElementById('page-select');
    const alignmentSelect = document.getElementById('alignment');
    const lengthSnapSelect = document.getElementById('length-snap');
    const lengthInput = document.getElementById('length');
     const orientationRadios = document.querySelectorAll('input[name="orientation"]');
     const fillColorInput = document.getElementById('fill-color');
     const resetButton = document.getElementById('reset-preview');
     const rotateCcwButton = document.getElementById('rotate-ccw');
     const rotateCwButton = document.getElementById('rotate-cw');
     const previewContainer = document.querySelector('.preview-container');

    // Hidden inputs
     const previewAlignment = document.getElementById('preview_alignment');
     const previewLengthSnap = document.getElementById('preview_length_snap');
     const previewOrientation = document.getElementById('preview_orientation');
     const previewRotation = document.getElementById('preview_rotation');
     const previewFillColor = document.getElementById('preview_fill_color');
     const previewPageNumber = document.getElementById('preview_page_number');

    // Bleed configuration from backend (global variable)
    // Load configuration from window.bleedConfig with proper fallback
    const bleedConfig = (function() {
        const windowConfig = window.bleedConfig;
        console.log('window.bleedConfig:', windowConfig);
        
        // If windowConfig is undefined or null, use defaults
        if (!windowConfig) {
            console.warn('window.bleedConfig is undefined/null, using defaults');
            return {
                paper_width: 12.0,
                paper_height: 18.0,
                bleed_margin: 0.125,
                safe_margin: 0.25,
                trim_top: 0.25,
                trim_bottom: 0.5,
                trim_left: 0.5,
                trim_right: 0.5,
                default_fill_color: '#FFFFFF',
                standard_lengths: [11.0, 13.75, 17.0]
            };
        }
        
        // If windowConfig is an empty object, also use defaults
        if (Object.keys(windowConfig).length === 0) {
            console.warn('window.bleedConfig is empty object, using defaults');
            return {
                paper_width: 12.0,
                paper_height: 18.0,
                bleed_margin: 0.125,
                safe_margin: 0.25,
                trim_top: 0.25,
                trim_bottom: 0.5,
                trim_left: 0.5,
                trim_right: 0.5,
                default_fill_color: '#FFFFFF',
                standard_lengths: [11.0, 13.75, 17.0]
            };
        }
        
        console.log('Using configuration from window.bleedConfig');
        return windowConfig;
    })();

    // Helper functions
    function isPdfFile(file) {
        return file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
    }

    function isImageFile(file) {
        const imageTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/tiff'];
        const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'];
        return imageTypes.includes(file.type) || imageExtensions.some(ext => file.name.toLowerCase().endsWith(ext));
    }

    // Initialize
    function init() {
        if (!pdfFileInput || !previewContainer) {
            return; // Not on upload page
        }

        // Debug: log loaded configuration
        console.log('Bleed configuration loaded:', bleedConfig);
        console.log('Trim values:', {
            top: bleedConfig.trim_top,
            bottom: bleedConfig.trim_bottom,
            left: bleedConfig.trim_left,
            right: bleedConfig.trim_right
        });
        
        // Warn if configuration appears empty (using fallback defaults)
        if (Object.keys(bleedConfig).length === 0) {
            console.warn('WARNING: Bleed configuration is empty! Using fallback defaults.');
        } else if (bleedConfig.trim_top === undefined) {
            console.warn('WARNING: trim_top not found in configuration. Using fallback.');
        }

        // Set default values
        fillColorInput.value = bleedConfig.default_fill_color || '#ffffff';
        updateHiddenInputs();

        // Event listeners
        pdfFileInput.addEventListener('change', handleFileSelect);
        pageSelect.addEventListener('change', handlePageChange);
        alignmentSelect.addEventListener('change', function() {
            console.log('Alignment changed to:', alignmentSelect.value, 'currentPage:', currentPage, 'isImageMode:', isImageMode);
            if (currentPage) {
                loadPage(currentPageNum);
            } else if (isImageMode && currentImage) {
                renderImage(currentImage);
            }
        });
        lengthSnapSelect.addEventListener('change', handleLengthSnapChange);
         fillColorInput.addEventListener('input', function() {
             if (currentPage) {
                 loadPage(currentPageNum);
             } else if (isImageMode && currentImage) {
                 renderImage(currentImage);
             }
             updateOverlay();
         });
          orientationRadios.forEach(radio => radio.addEventListener('change', function() {
             if (currentPage) {
                 loadPage(currentPageNum);
             } else if (isImageMode && currentImage) {
                 renderImage(currentImage);
             }
          }));
         resetButton.addEventListener('click', resetPreview);
         if (rotateCcwButton) rotateCcwButton.addEventListener('click', rotateCcw);
         if (rotateCwButton) rotateCwButton.addEventListener('click', rotateCw);

        // Initialize canvas
        initCanvas();

        // Update hidden inputs on any control change
        [alignmentSelect, lengthSnapSelect, fillColorInput].forEach(el => {
            el.addEventListener('change', updateHiddenInputs);
        });
        orientationRadios.forEach(radio => {
            radio.addEventListener('change', updateHiddenInputs);
        });
    }

    function updateLengthField(pageHeightPoints) {
        // Convert points to inches (72 points per inch)
        const lengthInches = pageHeightPoints / 72;
        let snappedLength = lengthInches;

        // Apply snapping if selected
        const snapValue = lengthSnapSelect.value;
        if (snapValue) {
            const target = parseFloat(snapValue);
            // Find closest standard length within tolerance (0.5 inch)
            const tolerance = 0.5;
            if (Math.abs(lengthInches - target) <= tolerance) {
                snappedLength = target;
            }
        }

        // Update length input field
        if (lengthInput) {
            lengthInput.value = snappedLength.toFixed(2);
        }
    }

    function handleLengthSnapChange() {
        if (currentPageHeightPoints) {
            updateLengthField(currentPageHeightPoints);
        }
        // Re-render with new length snap
        if (currentPage) {
            loadPage(currentPageNum);
        } else if (isImageMode && currentImage) {
            renderImage(currentImage);
        }
        updateOverlay();
    }

    function initCanvas() {
        // Create canvas elements if not present
        if (!canvas) {
            canvas = document.getElementById('pdf-canvas');
            overlay = document.getElementById('overlay-canvas');
            if (!canvas || !overlay) {
                // Create them dynamically
                const container = previewContainer;
                canvas = document.createElement('canvas');
                canvas.id = 'pdf-canvas';
                canvas.style.display = 'block';
                overlay = document.createElement('canvas');
                overlay.id = 'overlay-canvas';
                overlay.style.position = 'absolute';
                overlay.style.top = '0';
                overlay.style.left = '0';
                container.innerHTML = '';
                container.appendChild(canvas);
                container.appendChild(overlay);
            }
            ctx = canvas.getContext('2d');
            overlayCtx = overlay.getContext('2d');
        }
    }

    function handleFileSelect(event) {
        const file = event.target.files[0];
        if (!file) return;

        // Reset state
        resetPreview();

        // Check file type
        if (isPdfFile(file)) {
            // Load PDF
            const fileReader = new FileReader();
            fileReader.onload = function(e) {
                const typedarray = new Uint8Array(e.target.result);
                loadPdf(typedarray);
            };
            fileReader.readAsArrayBuffer(file);
        } else if (isImageFile(file)) {
            // Load image
            loadImage(file);
        } else {
            alert('Unsupported file type. Please upload a PDF or image file.');
            // Clear file input
            event.target.value = '';
        }
    }

    function loadPdf(data) {
        // Show page selection (in case hidden by image mode)
        if (pageSelect) pageSelect.style.display = '';
        const pageLabel = document.querySelector('label[for="page-select"]');
        if (pageLabel) pageLabel.style.display = '';
        // Hide image message
        if (previewContainer) {
            const message = previewContainer.querySelector('.image-message');
            if (message) message.style.display = 'none';
        }
        
        // Reset page select
        pageSelect.innerHTML = '<option>Loading...</option>';

        pdfjsLib.getDocument({ data }).promise.then(function(pdf) {
            pdfDoc = pdf;
            const numPages = pdf.numPages;

            // Populate page select
            pageSelect.innerHTML = '';
            for (let i = 1; i <= numPages; i++) {
                const option = document.createElement('option');
                option.value = i;
                option.textContent = `Page ${i}`;
                pageSelect.appendChild(option);
            }
            pageSelect.value = 1;
            previewPageNumber.value = 1;

            // Load first page
            loadPage(1);
        }).catch(function(error) {
            console.error('Error loading PDF:', error);
            alert('Failed to load PDF. Please ensure it is a valid PDF file.');
        });
    }

    function loadImage(file) {
        // Reset state
        isImageMode = true;
        pdfDoc = null;
        currentPage = null;
        currentImage = null;
        currentPageNum = 1;
        previewPageNumber.value = 1;
        
        // Hide page selection (images don't have pages)
        if (pageSelect) {
            pageSelect.style.display = 'none';
            const pageLabel = document.querySelector('label[for="page-select"]');
            if (pageLabel) pageLabel.style.display = 'none';
        }
        
        // Show image mode indicator
        let message = previewContainer.querySelector('.image-message');
        if (!message) {
            message = document.createElement('div');
            message.className = 'image-message alert alert-info mt-2';
            message.style.position = 'absolute';
            message.style.top = '10px';
            message.style.left = '10px';
            message.style.zIndex = '100';
            previewContainer.appendChild(message);
        }
        message.textContent = 'Image file: ' + file.name;
        message.style.display = 'block';
        
        // Create image object
        const img = new Image();
        img.onload = function() {
            // Store reference for rotation updates
            currentImage = img;
            // Set dimensions in points (assuming 72 DPI)
            currentPageWidthPoints = img.width;
            currentPageHeightPoints = img.height;
            
            // Determine orientation
            const isLandscape = img.width > img.height;
            const orientation = isLandscape ? 'landscape' : 'portrait';
            setOrientationRadio(orientation);
            
            // Calculate rotated dimensions for length field and scaling
            let rotatedWidth = img.width;
            let rotatedHeight = img.height;
            if (rotationAngle === 90 || rotationAngle === 270) {
                rotatedWidth = img.height;
                rotatedHeight = img.width;
            }
            updateLengthField(rotatedHeight);
            
            // Render image with current settings
            renderImage(img);
        };
        img.onerror = function() {
            alert('Failed to load image. Please ensure it is a valid image file.');
            // Reset file input
            pdfFileInput.value = '';
        };
        img.src = URL.createObjectURL(file);
    }

    function renderImage(img) {
        console.log('Rendering image, dimensions:', img.width, img.height);
        
        // Cancel any previous PDF render
        if (renderTask) {
            renderTask.cancel();
        }
        
        // Calculate scaling to fit container (similar to loadPage)
        const containerWidth = previewContainer.clientWidth - 20; // padding
        const containerHeight = previewContainer.clientHeight - 20;
        
        // Get content dimensions (points) with length snap consideration
        const contentDims = getContentDimensions();
        if (!contentDims) return;
        
        const {
            contentWidthPoints,
            contentHeightPoints,
            effectiveBottomY,
            cutLineY,
            trimTopPoints,
            trimBottomPoints,
            trimLeftPoints,
            trimRightPoints,
            paperWidthPoints,
            paperHeightPoints
        } = contentDims;
        
        // Scale paper to fit container
        const paperScaleX = containerWidth / paperWidthPoints;
        const paperScaleY = containerHeight / paperHeightPoints;
        paperScale = Math.min(paperScaleX, paperScaleY, 1.5); // Limit zoom
        
        // Determine rotated dimensions
        let rotatedWidth = img.width;
        let rotatedHeight = img.height;
        if (rotationAngle === 90 || rotationAngle === 270) {
            rotatedWidth = img.height;
            rotatedHeight = img.width;
        }
        // Update length field based on rotated height
        updateLengthField(rotatedHeight);
        
        // Scale image to fit within content area (maintain aspect ratio)
        const imageScaleX = contentWidthPoints / rotatedWidth;
        const imageScaleY = contentHeightPoints / rotatedHeight;
        const imageScale = Math.min(imageScaleX, imageScaleY);
        
        const scaledImageWidth = rotatedWidth * imageScale;
        const scaledImageHeight = rotatedHeight * imageScale;
        
        // Horizontal centering within trim lines
        const offsetXPoints = trimLeftPoints + (contentWidthPoints - scaledImageWidth) / 2;
        
        // Vertical alignment relative to trim lines
        let offsetYPoints;
        const alignment = alignmentSelect.value;
        if (alignment === 'top') {
            // Align top of image with top trim line
            offsetYPoints = trimTopPoints;
        } else if (alignment === 'bottom') {
            // Align bottom of image with effective bottom (trim line or cut line)
            offsetYPoints = effectiveBottomY - scaledImageHeight;
        } else { // middle (default)
            // Center between top and bottom trim lines
            offsetYPoints = trimTopPoints + (contentHeightPoints - scaledImageHeight) / 2;
        }
        
        // Convert to canvas pixels
        const offsetXCanvas = offsetXPoints * paperScale;
        const offsetYCanvas = offsetYPoints * paperScale;
        const imageScaleCanvas = imageScale * paperScale;
        const scaledImageWidthCanvas = scaledImageWidth * paperScale;
        const scaledImageHeightCanvas = scaledImageHeight * paperScale;
        lastPosterRect = {
            x: offsetXCanvas,
            y: offsetYCanvas,
            width: scaledImageWidthCanvas,
            height: scaledImageHeightCanvas
        };
        console.log('Image rectangle (canvas pixels):', lastPosterRect);
        
        // Set canvas dimensions to paper size (scaled)
        canvas.width = paperWidthPoints * paperScale;
        canvas.height = paperHeightPoints * paperScale;
        overlay.width = canvas.width;
        overlay.height = canvas.height;
        
        // Clear and fill canvas with fill color
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = fillColorInput.value;
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        // Draw image with translation and rotation
        ctx.save();
        ctx.translate(offsetXCanvas, offsetYCanvas);
        
        // Apply rotation
        if (rotationAngle !== 0) {
            // Rotate around center of image
            ctx.translate(scaledImageWidthCanvas / 2, scaledImageHeightCanvas / 2);
            ctx.rotate(rotationAngle * Math.PI / 180);
            ctx.translate(-scaledImageWidthCanvas / 2, -scaledImageHeightCanvas / 2);
        }
        
        // Draw image
        ctx.drawImage(img, 0, 0, scaledImageWidthCanvas, scaledImageHeightCanvas);
        ctx.restore();
        
        // Update overlay
        updateOverlay();
    }

    function loadPage(pageNum) {
        console.log('loadPage called, pageNum:', pageNum, 'pdfDoc:', pdfDoc);
        if (!pdfDoc) return;

        // Cancel previous render
        if (renderTask) {
            renderTask.cancel();
        }

        currentPageNum = pageNum;
        previewPageNumber.value = pageNum;

        pdfDoc.getPage(pageNum).then(function(page) {
            currentPage = page;

             // Calculate scaling to fit container
              console.log('Container raw:', {clientWidth: previewContainer.clientWidth, clientHeight: previewContainer.clientHeight});
              const containerWidth = previewContainer.clientWidth - 20; // padding
              const containerHeight = previewContainer.clientHeight - 20;
              console.log('Container dimensions:', {containerWidth, containerHeight});

              const pageWidth = page.view[2];
              const pageHeight = page.view[3];
              currentPageWidthPoints = pageWidth;
              currentPageHeightPoints = pageHeight;

              // Determine orientation
              const isLandscape = pageWidth > pageHeight;
              const orientation = isLandscape ? 'landscape' : 'portrait';
              setOrientationRadio(orientation);

                // Calculate rotated dimensions for length field and scaling
                let rotatedWidth = pageWidth;
                let rotatedHeight = pageHeight;
                if (rotationAngle === 90 || rotationAngle === 270) {
                    rotatedWidth = pageHeight;
                    rotatedHeight = pageWidth;
                }
                // Update length field based on rotated height (inches)
                updateLengthField(rotatedHeight);

              // Get content dimensions (points) with length snap consideration
              const contentDims = getContentDimensions();
              if (!contentDims) return;
              
              const {
                  contentWidthPoints,
                  contentHeightPoints,
                  effectiveBottomY,
                  cutLineY,
                  trimTopPoints,
                  trimBottomPoints,
                  trimLeftPoints,
                  trimRightPoints,
                  paperWidthPoints,
                  paperHeightPoints
              } = contentDims;
              
              console.log('Trim points (pts):', { trimTopPoints, trimBottomPoints, trimLeftPoints, trimRightPoints });
              console.log('Trim inches:', { 
                  top: bleedConfig.trim_top, 
                  bottom: bleedConfig.trim_bottom, 
                  left: bleedConfig.trim_left, 
                  right: bleedConfig.trim_right 
              });

              // Scale paper to fit container
              const paperScaleX = containerWidth / paperWidthPoints;
              const paperScaleY = containerHeight / paperHeightPoints;
              paperScale = Math.min(paperScaleX, paperScaleY, 1.5); // Limit zoom



              // Scale PDF to fit within content area (maintain aspect ratio)
              const pdfScaleX = contentWidthPoints / rotatedWidth;
              const pdfScaleY = contentHeightPoints / rotatedHeight;
              const pdfScale = Math.min(pdfScaleX, pdfScaleY);

              const scaledPdfWidth = rotatedWidth * pdfScale;
              const scaledPdfHeight = rotatedHeight * pdfScale;

              // Horizontal centering within trim lines
              const offsetXPoints = trimLeftPoints + (contentWidthPoints - scaledPdfWidth) / 2;
              
               // Vertical alignment relative to trim lines
               let offsetYPoints;
               const alignment = alignmentSelect.value;
               if (alignment === 'top') {
                   // Align top of poster with top trim line
                   offsetYPoints = trimTopPoints;
                } else if (alignment === 'bottom') {
                    // Align bottom of poster with effective bottom (trim line or cut line)
                    offsetYPoints = effectiveBottomY - scaledPdfHeight;
               } else { // middle (default)
                   // Center between top and bottom trim lines
                   offsetYPoints = trimTopPoints + (contentHeightPoints - scaledPdfHeight) / 2;
               }

               // Convert to canvas pixels
               const offsetXCanvas = offsetXPoints * paperScale;
               const offsetYCanvas = offsetYPoints * paperScale;
                const pdfScaleCanvas = pdfScale * paperScale;
                const scaledPdfWidthCanvas = scaledPdfWidth * paperScale;
                const scaledPdfHeightCanvas = scaledPdfHeight * paperScale;
                lastPosterRect = {
                    x: offsetXCanvas,
                    y: offsetYCanvas,
                    width: scaledPdfWidthCanvas,
                    height: scaledPdfHeightCanvas
                };
                console.log('Poster rectangle (canvas pixels):', lastPosterRect);

                // Debug logging
               console.log('Scaling calculations:', {
                   rotatedWidth, rotatedHeight,
                   contentWidthPoints, contentHeightPoints,
                   pdfScale, scaledPdfWidth, scaledPdfHeight,
                   trimLeftPoints, trimTopPoints, trimRightPoints, trimBottomPoints,
                   offsetXPoints, offsetYPoints, alignment: alignmentSelect.value,
                   paperScale, offsetXCanvas, offsetYCanvas
               });

               // Set canvas dimensions to paper size (scaled)
               canvas.width = paperWidthPoints * paperScale;
               canvas.height = paperHeightPoints * paperScale;
               overlay.width = canvas.width;
               overlay.height = canvas.height;

                // Clear and fill canvas with fill color
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.fillStyle = fillColorInput.value;
                ctx.fillRect(0, 0, canvas.width, canvas.height);

                  // Render PDF with translation and rotation
                 const viewport = page.getViewport({ scale: pdfScaleCanvas, rotation: rotationAngle });
                 
                 // DEBUG: Log transformation details
                 console.log('Rendering details:', {
                     offsetXCanvas, offsetYCanvas, 
                     pdfScaleCanvas,
                     viewportWidth: viewport.width,
                     viewportHeight: viewport.height,
                     viewportTransform: viewport.transform,
                     canvasWidth: canvas.width,
                     canvasHeight: canvas.height
                 });
                 
                 ctx.save();
                 
                 // DEBUG: Check initial transform
                 const initialTransform = ctx.getTransform();
                 console.log('Initial transform:', initialTransform);
                 
                 ctx.translate(offsetXCanvas, offsetYCanvas);
                 
                 // DEBUG: Check transform after translation
                 const afterTranslateTransform = ctx.getTransform();
                 console.log('Transform after translate:', afterTranslateTransform);
                 console.log('Expected translation:', offsetXCanvas, offsetYCanvas);
                 console.log('Actual translation from matrix:', afterTranslateTransform.e, afterTranslateTransform.f);
                 
                 // DEBUG: Draw a large semi-transparent blue rectangle to verify translation
                 ctx.save();
                 ctx.fillStyle = 'rgba(0, 0, 255, 0.2)';
                 ctx.fillRect(0, 0, viewport.width, viewport.height);
                 ctx.restore();
                 
                 // DEBUG: Draw a red rectangle at translation origin to visualize position
                 ctx.save();
                 ctx.fillStyle = 'rgba(255, 0, 0, 0.5)';
                 ctx.fillRect(0, 0, 20, 20);
                 ctx.restore();
                 
                 console.log('Calling PDF.js render with viewport scale:', pdfScaleCanvas);
                 renderTask = page.render({ canvasContext: ctx, viewport });
                 ctx.restore();

            // Draw overlay after render completes
            renderTask.promise.then(function() {
                updateOverlay();
            });
        });
    }

    function handlePageChange(event) {
        const pageNum = parseInt(event.target.value);
        if (pageNum && pdfDoc) {
            loadPage(pageNum);
        }
    }

    function updateOverlay() {
        if (!overlayCtx || (!currentPage && !isImageMode)) return;

        // Clear overlay
        overlayCtx.clearRect(0, 0, overlay.width, overlay.height);

        // Draw trim guides
         drawTrimGuides();

        // Draw alignment indicators
        drawAlignmentGuides();

         // Update hidden inputs
         updateHiddenInputs();
     }

     function rotateCcw() {
         rotationAngle = (rotationAngle - 90 + 360) % 360;
         updateRotation();
     }

     function rotateCw() {
         rotationAngle = (rotationAngle + 90) % 360;
         updateRotation();
     }

     function updateRotation() {
          previewRotation.value = rotationAngle;
          // Re-render page with new rotation
          if (currentPage) {
              loadPage(currentPageNum);
          } else if (isImageMode && currentImage) {
              renderImage(currentImage);
          }
      }

      function drawTrimGuides() {
         const trimCoords = calculateTrimCoordinates();
        if (!trimCoords) return;
        
        const { topY, bottomY, leftX, rightX, paperWidthScaled, paperHeightScaled, cutLineY } = trimCoords;

        // Draw paper outline (blue solid)
        overlayCtx.strokeStyle = '#0000ff';
        overlayCtx.lineWidth = 2;
        overlayCtx.setLineDash([]);
        overlayCtx.strokeRect(0, 0, paperWidthScaled, paperHeightScaled);

        // Draw trim lines (red dashed)
        overlayCtx.strokeStyle = '#ff0000';
        overlayCtx.lineWidth = 1;
        overlayCtx.setLineDash([5, 5]);
        
        // Top trim line
        overlayCtx.beginPath();
        overlayCtx.moveTo(leftX, topY);
        overlayCtx.lineTo(rightX, topY);
        overlayCtx.stroke();
        
        // Bottom trim line
        overlayCtx.beginPath();
        overlayCtx.moveTo(leftX, bottomY);
        overlayCtx.lineTo(rightX, bottomY);
        overlayCtx.stroke();
        
        // Draw cut line if length snap is active
        if (cutLineY && cutLineY !== bottomY) {
            overlayCtx.strokeStyle = '#ff00ff';
            overlayCtx.lineWidth = 2;
            overlayCtx.setLineDash([3, 3]);
            overlayCtx.beginPath();
            overlayCtx.moveTo(leftX, cutLineY);
            overlayCtx.lineTo(rightX, cutLineY);
            overlayCtx.stroke();
            // Draw label
            overlayCtx.fillStyle = '#ff00ff';
            overlayCtx.font = '10px Arial';
            overlayCtx.fillText(`Cut line (${lengthSnapSelect.value}")`, leftX + 5, cutLineY - 5);
        }
        
        // Left trim line
        overlayCtx.beginPath();
        overlayCtx.moveTo(leftX, topY);
        overlayCtx.lineTo(leftX, bottomY);
        overlayCtx.stroke();
        
         // Right trim line
         overlayCtx.beginPath();
         overlayCtx.moveTo(rightX, topY);
         overlayCtx.lineTo(rightX, bottomY);
         overlayCtx.stroke();

         // Draw content area rectangle (green dotted)
         overlayCtx.strokeStyle = '#00ff00';
         overlayCtx.lineWidth = 1;
         overlayCtx.setLineDash([2, 2]);
         overlayCtx.strokeRect(leftX, topY, rightX - leftX, bottomY - topY);
         // Draw label
         overlayCtx.fillStyle = '#00ff00';
         overlayCtx.font = '10px Arial';
         overlayCtx.fillText('Content area', leftX + 5, topY + 15);

         // Reset line dash
         overlayCtx.setLineDash([]);
    }

    function drawAlignmentGuides() {
        const width = overlay.width;
        const height = overlay.height;
        const alignment = alignmentSelect.value;
        
        // Get trim coordinates in canvas pixels
         const trimCoords = calculateTrimCoordinates();
        if (!trimCoords) return;
        
        const { topY, bottomY, leftX, rightX } = trimCoords;
        const trimHeight = bottomY - topY;
        
        // Draw horizontal alignment line within trim area
        overlayCtx.strokeStyle = '#ff9900';
        overlayCtx.lineWidth = 1;
        overlayCtx.setLineDash([3, 3]);

        let y;
        if (alignment === 'top') {
            y = topY;
        } else if (alignment === 'bottom') {
            y = bottomY;
        } else { // middle - center between top and bottom trim lines
            y = topY + trimHeight / 2;
        }

        overlayCtx.beginPath();
        overlayCtx.moveTo(leftX, y);
        overlayCtx.lineTo(rightX, y);
        overlayCtx.stroke();

        // Draw label
        overlayCtx.fillStyle = '#ff9900';
        overlayCtx.font = '12px Arial';
        overlayCtx.fillText(`${alignment} alignment`, leftX + 5, y - 5);

        // Draw poster rectangle (cyan) if available
        if (lastPosterRect) {
            overlayCtx.save();
            overlayCtx.strokeStyle = 'cyan';
            overlayCtx.lineWidth = 2;
            overlayCtx.setLineDash([]);
            overlayCtx.strokeRect(lastPosterRect.x, lastPosterRect.y, lastPosterRect.width, lastPosterRect.height);
            overlayCtx.fillStyle = 'cyan';
            overlayCtx.font = '10px Arial';
            overlayCtx.fillText('Poster', lastPosterRect.x + 5, lastPosterRect.y + 15);
            overlayCtx.restore();
        }

        overlayCtx.setLineDash([]);
    }
    
       function calculateTrimCoordinates() {
          // Get trim and paper dimensions from bleedConfig
          // Use defined check to allow 0 values
          const getTrimValue = (key) => {
              const value = bleedConfig[key];
              if (value !== undefined) return value;
              const safe = bleedConfig.safe_margin;
              if (safe !== undefined) return safe;
              return 0.5;
          };
          
          const trimTopInches = getTrimValue('trim_top');
          const trimBottomInches = getTrimValue('trim_bottom');
          const trimLeftInches = getTrimValue('trim_left');
          const trimRightInches = getTrimValue('trim_right');
          const paperWidthInches = bleedConfig.paper_width || 12.0;
          const paperHeightInches = bleedConfig.paper_height || 18.0;

          // Convert inches to points (72 points per inch)
          const trimTopPoints = trimTopInches * 72;
          const trimBottomPoints = trimBottomInches * 72;
          const trimLeftPoints = trimLeftInches * 72;
          const trimRightPoints = trimRightInches * 72;
          const paperWidthPoints = paperWidthInches * 72;
          const paperHeightPoints = paperHeightInches * 72;
          
          // Length snap cut line (points)
          let cutLinePoints = null;
          let effectiveBottomPoints = paperHeightPoints - trimBottomPoints;
          const lengthSnapValue = lengthSnapSelect.value;
          if (lengthSnapValue) {
              const lengthSnapInches = parseFloat(lengthSnapValue);
              cutLinePoints = trimTopPoints + (lengthSnapInches * 72);
              // If cut line is above original bottom trim, use cut line as effective bottom
              if (cutLinePoints < effectiveBottomPoints) {
                  effectiveBottomPoints = cutLinePoints;
              }
          }

          // Debug logging
          console.log('Trim config:', { trimTopInches, trimBottomInches, trimLeftInches, trimRightInches });
          console.log('Paper dimensions:', { paperWidthInches, paperHeightInches });
          console.log('Trim points:', { trimTopPoints, trimBottomPoints, trimLeftPoints, trimRightPoints });
          console.log('Cut line points:', cutLinePoints);
          console.log('Content area points:', { 
              contentWidth: paperWidthPoints - trimLeftPoints - trimRightPoints,
              contentHeight: effectiveBottomPoints - trimTopPoints
          });

          // Scale to canvas pixels using paperScale (global)
          const topY = trimTopPoints * paperScale;
          const bottomY = effectiveBottomPoints * paperScale;
          const leftX = trimLeftPoints * paperScale;
          const rightX = (paperWidthPoints - trimRightPoints) * paperScale;
          const paperWidthScaled = paperWidthPoints * paperScale;
          const paperHeightScaled = paperHeightPoints * paperScale;
          const cutLineY = cutLinePoints ? cutLinePoints * paperScale : null;
          
          return {
              topY,
              bottomY,
              leftX,
              rightX,
              paperWidthScaled,
              paperHeightScaled,
              cutLineY,
              trimTopPoints,
              trimBottomPoints,
              trimLeftPoints,
              trimRightPoints,
              paperWidthPoints,
              paperHeightPoints,
              effectiveBottomPoints
          };
      }

       function getContentDimensions() {
           const trimCoords = calculateTrimCoordinates();
           if (!trimCoords) return null;
           
           const { trimTopPoints, trimBottomPoints, trimLeftPoints, trimRightPoints, paperWidthPoints, paperHeightPoints, effectiveBottomPoints, cutLineY } = trimCoords;
           
           // Content dimensions (within effective trim lines, considering length snap)
           const contentWidthPoints = paperWidthPoints - trimLeftPoints - trimRightPoints;
           const contentHeightPoints = effectiveBottomPoints - trimTopPoints;
           const cutLinePoints = cutLineY ? cutLineY / paperScale : null;
           
           return {
               contentWidthPoints,
               contentHeightPoints,
               effectiveBottomY: effectiveBottomPoints,
               cutLineY: cutLinePoints,
               trimTopPoints,
               trimBottomPoints,
               trimLeftPoints,
               trimRightPoints,
               paperWidthPoints,
               paperHeightPoints
           };
       }

    function setOrientationRadio(value) {
        const radio = document.querySelector(`input[name="orientation"][value="${value}"]`);
        if (radio) {
            radio.checked = true;
        }
    }

     function updateHiddenInputs() {
         previewAlignment.value = alignmentSelect.value;
         previewLengthSnap.value = lengthSnapSelect.value;
         previewFillColor.value = fillColorInput.value;
         previewRotation.value = rotationAngle;

         const selectedOrientation = document.querySelector('input[name="orientation"]:checked');
         previewOrientation.value = selectedOrientation ? selectedOrientation.value : 'auto';
     }

       function resetPreview() {
           // Reset controls to defaults
           alignmentSelect.value = 'middle';
           lengthSnapSelect.value = '';
           fillColorInput.value = bleedConfig.default_fill_color || '#ffffff';
           setOrientationRadio('auto');
           rotationAngle = 0;
           previewRotation.value = rotationAngle;
           
           // Reset image mode
           isImageMode = false;
           currentPageWidthPoints = 0;
           currentPageHeightPoints = 0;
           
           // Show page selection (in case hidden by image mode)
           if (pageSelect) pageSelect.style.display = '';
           const pageLabel = document.querySelector('label[for="page-select"]');
           if (pageLabel) pageLabel.style.display = '';
           
           // Hide image message
           if (previewContainer) {
               const message = previewContainer.querySelector('.image-message');
               if (message) message.style.display = 'none';
           }

           // Update overlay
           updateOverlay();
       }

    // Start when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();