/**
 * GuapoSniper Fight Lab - Main Application
 *
 * Handles:
 * - Camera access and video stream
 * - Video file upload
 * - MediaPipe Pose initialization
 * - Real-time pose overlay drawing
 * - UI updates with analysis results
 */

(function () {
    'use strict';

    // ========== DOM ELEMENTS ==========
    const videoElement = document.getElementById('videoElement');
    const overlayCanvas = document.getElementById('overlayCanvas');
    const ctx = overlayCanvas.getContext('2d');
    const videoPlaceholder = document.getElementById('videoPlaceholder');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const loadingText = document.getElementById('loadingText');
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');
    const analysisPanel = document.getElementById('analysisPanel');

    // Mode buttons
    const modeLive = document.getElementById('modeLive');
    const modeUpload = document.getElementById('modeUpload');

    // Live controls
    const btnStartCamera = document.getElementById('btnStartCamera');
    const btnStartAnalysis = document.getElementById('btnStartAnalysis');
    const btnStopAnalysis = document.getElementById('btnStopAnalysis');
    const liveControls = document.getElementById('liveControls');

    // Upload controls
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    const uploadControls = document.getElementById('uploadControls');
    const btnAnalyzeVideo = document.getElementById('btnAnalyzeVideo');
    const btnStopUploadAnalysis = document.getElementById('btnStopUploadAnalysis');

    // Score elements
    const scoreCircle = document.getElementById('scoreCircle');
    const scoreLabel = document.getElementById('scoreLabel');

    // ========== STATE ==========
    let pose = null;
    let camera = null;
    let isAnalyzing = false;
    let currentMode = 'live'; // 'live' or 'upload'
    let uploadedVideoUrl = null;
    let animFrameId = null;

    // ========== MEDIAPIPE POSE SETUP ==========
    function initPose() {
        loadingOverlay.classList.remove('hidden');
        loadingText.textContent = 'Chargement du modele IA...';

        pose = new Pose({
            locateFile: (file) => {
                return `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`;
            }
        });

        pose.setOptions({
            modelComplexity: 1,
            smoothLandmarks: true,
            enableSegmentation: false,
            minDetectionConfidence: 0.5,
            minTrackingConfidence: 0.5
        });

        pose.onResults(onPoseResults);

        pose.initialize().then(() => {
            loadingOverlay.classList.add('hidden');
            setStatus('Modele IA pret', 'active');
        }).catch((err) => {
            loadingText.textContent = 'Erreur de chargement du modele.';
            console.error('Pose init error:', err);
        });
    }

    // ========== POSE RESULTS CALLBACK ==========
    function onPoseResults(results) {
        // Resize canvas to match video
        overlayCanvas.width = videoElement.videoWidth || videoElement.clientWidth;
        overlayCanvas.height = videoElement.videoHeight || videoElement.clientHeight;

        ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);

        if (!results.poseLandmarks) return;

        // Draw skeleton
        drawSkeleton(results.poseLandmarks);

        // Run kickboxing analysis
        if (isAnalyzing) {
            const analysis = KickboxingAnalyzer.analyze(results.poseLandmarks);
            if (analysis) {
                updateUI(analysis);
            }
        }
    }

    // ========== SKELETON DRAWING ==========
    const POSE_CONNECTIONS = [
        [11, 12], // shoulders
        [11, 13], [13, 15], // left arm
        [12, 14], [14, 16], // right arm
        [11, 23], [12, 24], // torso
        [23, 24], // hips
        [23, 25], [25, 27], // left leg
        [24, 26], [26, 28], // right leg
    ];

    function drawSkeleton(landmarks) {
        const w = overlayCanvas.width;
        const h = overlayCanvas.height;

        // Draw connections
        ctx.lineWidth = 3;
        for (const [a, b] of POSE_CONNECTIONS) {
            const la = landmarks[a];
            const lb = landmarks[b];
            if (la.visibility < 0.4 || lb.visibility < 0.4) continue;

            ctx.beginPath();
            ctx.moveTo(la.x * w, la.y * h);
            ctx.lineTo(lb.x * w, lb.y * h);
            ctx.strokeStyle = 'rgba(0, 255, 204, 0.7)';
            ctx.stroke();
        }

        // Draw landmarks
        for (let i = 0; i < landmarks.length; i++) {
            const lm = landmarks[i];
            if (lm.visibility < 0.4) continue;
            // Skip face landmarks except nose
            if (i > 0 && i < 11) continue;

            const x = lm.x * w;
            const y = lm.y * h;
            const radius = (i === 0) ? 8 : 6;

            // Color based on importance
            let color = 'rgba(0, 255, 204, 0.9)';
            if (i === 15 || i === 16) color = '#ff4757'; // Wrists - highlight
            if (i === 27 || i === 28) color = '#ffa502'; // Ankles - highlight

            ctx.beginPath();
            ctx.arc(x, y, radius, 0, 2 * Math.PI);
            ctx.fillStyle = color;
            ctx.fill();
            ctx.strokeStyle = 'rgba(0,0,0,0.5)';
            ctx.lineWidth = 2;
            ctx.stroke();
        }

        // Draw guard zone indicator (chin area)
        if (isAnalyzing) {
            const nose = landmarks[0];
            if (nose.visibility > 0.4) {
                const nx = nose.x * w;
                const ny = nose.y * h;
                ctx.beginPath();
                ctx.arc(nx, ny + 15, 35, 0, 2 * Math.PI);
                ctx.strokeStyle = 'rgba(0, 255, 204, 0.2)';
                ctx.lineWidth = 2;
                ctx.setLineDash([5, 5]);
                ctx.stroke();
                ctx.setLineDash([]);
            }
        }
    }

    // ========== UI UPDATES ==========
    function updateUI(analysis) {
        // Global score
        scoreCircle.textContent = analysis.global;
        scoreCircle.className = 'score-circle ' + getScoreClass(analysis.global);
        scoreLabel.textContent = getScoreText(analysis.global);

        // Update each defect card
        updateCard('Guard', analysis.guard);
        updateCard('Stance', analysis.stance);
        updateCard('Hips', analysis.hips);
        updateCard('Elbows', analysis.elbows);
        updateCard('Balance', analysis.balance);
        updateCard('Return', analysis.guardReturn);

        // Update tips
        updateTips(analysis.tips);

        // Show panel
        analysisPanel.classList.add('visible');
    }

    function updateCard(name, data) {
        const card = document.getElementById('card' + name);
        const status = document.getElementById('status' + name);
        const msg = document.getElementById('msg' + name);
        const meter = document.getElementById('meter' + name);

        card.className = 'defect-card ' + data.status;
        status.textContent = data.status === 'ok' ? 'OK' : data.status === 'warning' ? 'ATTENTION' : 'DEFAUT';
        msg.textContent = data.message;
        meter.style.width = data.score + '%';
    }

    function updateTips(tips) {
        const tipsList = document.getElementById('tipsList');
        if (!tips || tips.length === 0) {
            tipsList.innerHTML = '<div class="tip-item"><div class="tip-icon">&#x2705;</div><div class="tip-text">Bonne technique ! Continue comme ca.</div></div>';
            return;
        }

        tipsList.innerHTML = tips.map(tip => `
            <div class="tip-item">
                <div class="tip-icon">${tip.priority === 'high' ? '&#x26A0;' : '&#x1F4A1;'}</div>
                <div class="tip-text">${tip.text}</div>
            </div>
        `).join('');
    }

    function getScoreClass(score) {
        if (score >= 70) return 'good';
        if (score >= 45) return 'medium';
        return 'bad';
    }

    function getScoreText(score) {
        if (score >= 85) return 'Excellent';
        if (score >= 70) return 'Bien';
        if (score >= 55) return 'Moyen';
        if (score >= 40) return 'A ameliorer';
        return 'Critique';
    }

    function setStatus(text, state) {
        statusText.textContent = text;
        statusDot.className = 'status-dot' + (state ? ' ' + state : '');
    }

    // ========== MODE SWITCHING ==========
    function switchMode(mode) {
        stopAnalysis();
        currentMode = mode;

        modeLive.classList.toggle('active', mode === 'live');
        modeUpload.classList.toggle('active', mode === 'upload');

        if (mode === 'live') {
            liveControls.classList.remove('hidden');
            uploadControls.classList.add('hidden');
            uploadArea.style.display = 'none';
            document.getElementById('videoArea').style.display = '';
            videoPlaceholder.querySelector('p').textContent = 'Clique sur "Demarrer la camera" pour commencer';
        } else {
            liveControls.classList.add('hidden');
            uploadControls.classList.remove('hidden');
            uploadArea.style.display = 'block';
            stopCamera();
        }
    }

    modeLive.addEventListener('click', () => switchMode('live'));
    modeUpload.addEventListener('click', () => switchMode('upload'));

    // ========== CAMERA ==========
    async function startCamera() {
        try {
            setStatus('Acces camera...', '');
            loadingOverlay.classList.remove('hidden');
            loadingText.textContent = 'Acces a la camera...';

            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } },
                audio: false
            });

            videoElement.srcObject = stream;
            await videoElement.play();
            videoPlaceholder.classList.add('hidden');
            loadingOverlay.classList.add('hidden');

            btnStartCamera.disabled = true;
            btnStartCamera.textContent = '&#x2705; Camera active';
            btnStartAnalysis.disabled = false;

            setStatus('Camera active', 'active');
        } catch (err) {
            loadingOverlay.classList.add('hidden');
            setStatus('Erreur camera', '');
            alert('Impossible d\'acceder a la camera. Verifie les permissions de ton navigateur.');
            console.error('Camera error:', err);
        }
    }

    function stopCamera() {
        if (videoElement.srcObject) {
            videoElement.srcObject.getTracks().forEach(t => t.stop());
            videoElement.srcObject = null;
        }
        videoPlaceholder.classList.remove('hidden');
        btnStartCamera.disabled = false;
        btnStartCamera.innerHTML = '&#x1F4F7; Demarrer la camera';
        btnStartAnalysis.disabled = true;
    }

    btnStartCamera.addEventListener('click', startCamera);

    // ========== LIVE ANALYSIS ==========
    function startLiveAnalysis() {
        if (!pose) {
            initPose();
            // Wait for init then start
            const checkReady = setInterval(() => {
                if (pose && !loadingOverlay.classList.contains('hidden') === false) {
                    clearInterval(checkReady);
                    beginLiveLoop();
                }
            }, 200);

            setTimeout(() => {
                clearInterval(checkReady);
                beginLiveLoop();
            }, 5000);
            return;
        }
        beginLiveLoop();
    }

    function beginLiveLoop() {
        isAnalyzing = true;
        KickboxingAnalyzer.reset();
        analysisPanel.classList.add('visible');
        btnStartAnalysis.disabled = true;
        btnStopAnalysis.disabled = false;
        setStatus('Analyse en cours', 'recording');

        async function processFrame() {
            if (!isAnalyzing) return;
            if (videoElement.readyState >= 2) {
                await pose.send({ image: videoElement });
            }
            animFrameId = requestAnimationFrame(processFrame);
        }
        processFrame();
    }

    function stopAnalysis() {
        isAnalyzing = false;
        if (animFrameId) {
            cancelAnimationFrame(animFrameId);
            animFrameId = null;
        }
        btnStartAnalysis.disabled = !videoElement.srcObject;
        btnStopAnalysis.disabled = true;
        btnAnalyzeVideo.disabled = !uploadedVideoUrl;
        btnStopUploadAnalysis.disabled = true;
        ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
        setStatus('Analyse arretee', 'active');
    }

    btnStartAnalysis.addEventListener('click', startLiveAnalysis);
    btnStopAnalysis.addEventListener('click', stopAnalysis);

    // ========== FILE UPLOAD ==========
    uploadArea.addEventListener('click', () => fileInput.click());
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('drag-over');
    });
    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('drag-over');
    });
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('drag-over');
        const file = e.dataTransfer.files[0];
        if (file && file.type.startsWith('video/')) {
            handleVideoFile(file);
        }
    });
    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) handleVideoFile(file);
    });

    function handleVideoFile(file) {
        if (uploadedVideoUrl) URL.revokeObjectURL(uploadedVideoUrl);
        uploadedVideoUrl = URL.createObjectURL(file);

        videoElement.srcObject = null;
        videoElement.src = uploadedVideoUrl;
        videoElement.muted = true;
        videoElement.loop = true;
        videoElement.play();
        videoPlaceholder.classList.add('hidden');

        uploadArea.querySelector('p').innerHTML = '<strong>' + file.name + '</strong> charge !';
        btnAnalyzeVideo.disabled = false;

        setStatus('Video chargee', 'active');
    }

    btnAnalyzeVideo.addEventListener('click', () => {
        if (!pose) {
            initPose();
            setTimeout(() => startUploadAnalysis(), 4000);
            return;
        }
        startUploadAnalysis();
    });

    function startUploadAnalysis() {
        isAnalyzing = true;
        KickboxingAnalyzer.reset();
        analysisPanel.classList.add('visible');
        btnAnalyzeVideo.disabled = true;
        btnStopUploadAnalysis.disabled = false;
        videoElement.currentTime = 0;
        videoElement.play();
        setStatus('Analyse video en cours', 'recording');

        async function processFrame() {
            if (!isAnalyzing) return;
            if (videoElement.readyState >= 2) {
                await pose.send({ image: videoElement });
            }
            animFrameId = requestAnimationFrame(processFrame);
        }
        processFrame();
    }

    btnStopUploadAnalysis.addEventListener('click', stopAnalysis);

    // ========== INIT ==========
    // Pre-initialize pose model
    initPose();

})();
