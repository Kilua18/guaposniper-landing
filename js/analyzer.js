/**
 * GuapoSniper Fight Lab - Kickboxing Pose Analyzer
 *
 * Analyses MediaPipe Pose landmarks to detect common kickboxing defects:
 * - Guard position (hands protecting face)
 * - Stance width and base
 * - Hip rotation during strikes
 * - Elbow tucking
 * - Balance / weight distribution
 * - Guard return after strikes
 *
 * MediaPipe Pose Landmarks Reference:
 *  0: nose
 *  11/12: left/right shoulder
 *  13/14: left/right elbow
 *  15/16: left/right wrist
 *  23/24: left/right hip
 *  25/26: left/right knee
 *  27/28: left/right ankle
 */

const KickboxingAnalyzer = (function () {
    // Landmark indices
    const NOSE = 0;
    const L_SHOULDER = 11;
    const R_SHOULDER = 12;
    const L_ELBOW = 13;
    const R_ELBOW = 14;
    const L_WRIST = 15;
    const R_WRIST = 16;
    const L_HIP = 23;
    const R_HIP = 24;
    const L_KNEE = 25;
    const R_KNEE = 26;
    const L_ANKLE = 27;
    const R_ANKLE = 28;

    // History for temporal analysis
    let guardHistory = [];
    let hipHistory = [];
    let wristHistory = [];
    const HISTORY_SIZE = 30; // ~1 second at 30fps

    // Running averages for smoother feedback
    let scores = {
        guard: 100,
        stance: 100,
        hips: 100,
        elbows: 100,
        balance: 100,
        guardReturn: 100
    };

    const SMOOTHING = 0.15; // How fast scores update (0=frozen, 1=instant)

    function reset() {
        guardHistory = [];
        hipHistory = [];
        wristHistory = [];
        scores = {
            guard: 100,
            stance: 100,
            hips: 100,
            elbows: 100,
            balance: 100,
            guardReturn: 100
        };
    }

    function dist(a, b) {
        return Math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2);
    }

    function midpoint(a, b) {
        return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
    }

    function angle(a, b, c) {
        const ab = { x: a.x - b.x, y: a.y - b.y };
        const cb = { x: c.x - b.x, y: c.y - b.y };
        const dot = ab.x * cb.x + ab.y * cb.y;
        const magAB = Math.sqrt(ab.x ** 2 + ab.y ** 2);
        const magCB = Math.sqrt(cb.x ** 2 + cb.y ** 2);
        if (magAB === 0 || magCB === 0) return 0;
        const cosAngle = Math.max(-1, Math.min(1, dot / (magAB * magCB)));
        return Math.acos(cosAngle) * (180 / Math.PI);
    }

    function smooth(current, target) {
        return current + (target - current) * SMOOTHING;
    }

    /**
     * Main analysis function - call this with MediaPipe pose landmarks
     * Returns an analysis result object
     */
    function analyze(landmarks) {
        if (!landmarks || landmarks.length < 29) {
            return null;
        }

        const nose = landmarks[NOSE];
        const lShoulder = landmarks[L_SHOULDER];
        const rShoulder = landmarks[R_SHOULDER];
        const lElbow = landmarks[L_ELBOW];
        const rElbow = landmarks[R_ELBOW];
        const lWrist = landmarks[L_WRIST];
        const rWrist = landmarks[R_WRIST];
        const lHip = landmarks[L_HIP];
        const rHip = landmarks[R_HIP];
        const lKnee = landmarks[L_KNEE];
        const rKnee = landmarks[R_KNEE];
        const lAnkle = landmarks[L_ANKLE];
        const rAnkle = landmarks[R_ANKLE];

        // Reference measurement: shoulder width
        const shoulderWidth = dist(lShoulder, rShoulder);
        if (shoulderWidth < 0.01) return null; // Too small to analyze

        // ===== 1. GUARD ANALYSIS =====
        const guardScore = analyzeGuard(nose, lShoulder, rShoulder, lWrist, rWrist, shoulderWidth);

        // ===== 2. STANCE ANALYSIS =====
        const stanceScore = analyzeStance(lAnkle, rAnkle, lHip, rHip, shoulderWidth);

        // ===== 3. HIP ROTATION =====
        const hipsScore = analyzeHipRotation(lShoulder, rShoulder, lHip, rHip);

        // ===== 4. ELBOWS =====
        const elbowsScore = analyzeElbows(lShoulder, rShoulder, lElbow, rElbow, lWrist, rWrist, shoulderWidth);

        // ===== 5. BALANCE =====
        const balanceScore = analyzeBalance(nose, lShoulder, rShoulder, lHip, rHip, lAnkle, rAnkle);

        // ===== 6. GUARD RETURN =====
        const guardReturnScore = analyzeGuardReturn(lWrist, rWrist, nose, shoulderWidth);

        // Smooth all scores
        scores.guard = smooth(scores.guard, guardScore.score);
        scores.stance = smooth(scores.stance, stanceScore.score);
        scores.hips = smooth(scores.hips, hipsScore.score);
        scores.elbows = smooth(scores.elbows, elbowsScore.score);
        scores.balance = smooth(scores.balance, balanceScore.score);
        scores.guardReturn = smooth(scores.guardReturn, guardReturnScore.score);

        // Global score (weighted average)
        const globalScore = Math.round(
            scores.guard * 0.25 +
            scores.stance * 0.15 +
            scores.hips * 0.15 +
            scores.elbows * 0.15 +
            scores.balance * 0.15 +
            scores.guardReturn * 0.15
        );

        return {
            global: globalScore,
            guard: { score: Math.round(scores.guard), ...guardScore },
            stance: { score: Math.round(scores.stance), ...stanceScore },
            hips: { score: Math.round(scores.hips), ...hipsScore },
            elbows: { score: Math.round(scores.elbows), ...elbowsScore },
            balance: { score: Math.round(scores.balance), ...balanceScore },
            guardReturn: { score: Math.round(scores.guardReturn), ...guardReturnScore },
            tips: generateTips(scores)
        };
    }

    // ========== GUARD ANALYSIS ==========
    function analyzeGuard(nose, lShoulder, rShoulder, lWrist, rWrist, shoulderWidth) {
        // Check if wrists are near chin/face level
        // In normalized coords, lower Y = higher position
        const chinY = nose.y + 0.03;
        const shoulderY = (lShoulder.y + rShoulder.y) / 2;

        // Wrist height relative to chin-shoulder range
        const lWristHeight = 1 - Math.max(0, Math.min(1, (lWrist.y - chinY) / (shoulderY - chinY + 0.001)));
        const rWristHeight = 1 - Math.max(0, Math.min(1, (rWrist.y - chinY) / (shoulderY - chinY + 0.001)));

        // Distance from face center
        const faceCenterX = nose.x;
        const lDistFromFace = Math.abs(lWrist.x - faceCenterX) / shoulderWidth;
        const rDistFromFace = Math.abs(rWrist.x - faceCenterX) / shoulderWidth;

        // Hands too low?
        const heightScore = ((lWristHeight + rWristHeight) / 2) * 100;

        // Hands too far from face?
        const proximityScore = Math.max(0, 100 - (((lDistFromFace + rDistFromFace) / 2) - 0.3) * 150);

        const score = Math.max(0, Math.min(100, (heightScore * 0.6 + proximityScore * 0.4)));

        let message, status;
        if (score >= 75) {
            message = "Bonne garde ! Tes mains protegent bien ton visage.";
            status = "ok";
        } else if (score >= 45) {
            message = "Garde moyenne. Remonte tes mains au niveau du menton.";
            status = "warning";
        } else {
            message = "Garde trop basse ! Tes mains doivent etre au niveau du menton pour proteger ton visage.";
            status = "issue";
        }

        return { score, message, status };
    }

    // ========== STANCE ANALYSIS ==========
    function analyzeStance(lAnkle, rAnkle, lHip, rHip, shoulderWidth) {
        // Ideal stance width: roughly 1.2-1.8x shoulder width
        const feetWidth = Math.abs(lAnkle.x - rAnkle.x);
        const ratio = feetWidth / shoulderWidth;

        let score;
        if (ratio >= 1.0 && ratio <= 2.0) {
            score = 100 - Math.abs(ratio - 1.5) * 40; // Best around 1.5
        } else if (ratio < 1.0) {
            score = Math.max(0, ratio * 60); // Too narrow
        } else {
            score = Math.max(0, 100 - (ratio - 2.0) * 80); // Too wide
        }

        // Check feet are staggered (front/back)
        const feetDepth = Math.abs(lAnkle.y - rAnkle.y);
        const staggerBonus = Math.min(20, feetDepth / shoulderWidth * 80);
        score = Math.min(100, score + staggerBonus * 0.3);

        let message, status;
        if (score >= 75) {
            message = "Bonne stance. Base solide et equilibree.";
            status = "ok";
        } else if (score >= 45) {
            if (ratio < 1.0) {
                message = "Stance trop etroite. Ecarte davantage tes pieds pour plus de stabilite.";
            } else if (ratio > 2.0) {
                message = "Stance trop large. Resserre un peu pour garder ta mobilite.";
            } else {
                message = "Stance correcte mais ameliorable. Decale un pied pour une meilleure position de combat.";
            }
            status = "warning";
        } else {
            message = "Mauvaise stance ! Pieds a largeur d'epaules, un pied legerement devant l'autre.";
            status = "issue";
        }

        return { score: Math.max(0, Math.min(100, score)), message, status };
    }

    // ========== HIP ROTATION ==========
    function analyzeHipRotation(lShoulder, rShoulder, lHip, rHip) {
        // Measure shoulder-hip alignment difference to detect rotation
        const shoulderAngle = Math.atan2(rShoulder.y - lShoulder.y, rShoulder.x - lShoulder.x);
        const hipAngle = Math.atan2(rHip.y - lHip.y, rHip.x - lHip.x);
        const rotationDiff = Math.abs(shoulderAngle - hipAngle) * (180 / Math.PI);

        // Store in history
        hipHistory.push(rotationDiff);
        if (hipHistory.length > HISTORY_SIZE) hipHistory.shift();

        // Check for rotation variation over time (indicates active rotation)
        const maxRotation = Math.max(...hipHistory);
        const minRotation = Math.min(...hipHistory);
        const rotationRange = maxRotation - minRotation;

        // Good fighters have visible hip rotation when striking
        let score;
        if (hipHistory.length < 10) {
            score = 70; // Not enough data yet
        } else if (rotationRange > 8) {
            score = Math.min(100, 70 + rotationRange * 2);
        } else {
            score = Math.max(30, rotationRange * 8);
        }

        let message, status;
        if (score >= 75) {
            message = "Bonne rotation des hanches. Tu generes de la puissance dans tes coups.";
            status = "ok";
        } else if (score >= 45) {
            message = "Rotation insuffisante. Engage davantage tes hanches quand tu frappes.";
            status = "warning";
        } else {
            message = "Pas de rotation des hanches detectee. Tourne tes hanches avec chaque coup pour plus de puissance.";
            status = "issue";
        }

        return { score: Math.max(0, Math.min(100, score)), message, status };
    }

    // ========== ELBOWS ==========
    function analyzeElbows(lShoulder, rShoulder, lElbow, rElbow, lWrist, rWrist, shoulderWidth) {
        // Check elbow angle (should be tucked, ~45-90 degrees when in guard)
        const lElbowAngle = angle(lShoulder, lElbow, lWrist);
        const rElbowAngle = angle(rShoulder, rElbow, rWrist);

        // Check elbows aren't flared out too much
        const lElbowSpread = Math.abs(lElbow.x - lShoulder.x) / shoulderWidth;
        const rElbowSpread = Math.abs(rElbow.x - rShoulder.x) / shoulderWidth;

        // Ideal: elbows at ~30-90 degrees and close to body
        let angleScore = 0;
        const avgAngle = (lElbowAngle + rElbowAngle) / 2;
        if (avgAngle >= 30 && avgAngle <= 100) {
            angleScore = 100 - Math.abs(avgAngle - 65) * 1.5;
        } else {
            angleScore = Math.max(0, 50 - Math.abs(avgAngle - 65));
        }

        // Elbow spread penalty
        const avgSpread = (lElbowSpread + rElbowSpread) / 2;
        const spreadScore = avgSpread < 0.8 ? 100 : Math.max(0, 100 - (avgSpread - 0.8) * 200);

        const score = Math.max(0, Math.min(100, angleScore * 0.5 + spreadScore * 0.5));

        let message, status;
        if (score >= 75) {
            message = "Coudes bien places. Bonne protection du corps.";
            status = "ok";
        } else if (score >= 45) {
            message = "Coudes un peu ecartes. Garde-les plus pres de ton corps pour te proteger.";
            status = "warning";
        } else {
            message = "Coudes trop ecartes ! Tu exposes tes cotes. Colle tes coudes au corps.";
            status = "issue";
        }

        return { score, message, status };
    }

    // ========== BALANCE ==========
    function analyzeBalance(nose, lShoulder, rShoulder, lHip, rHip, lAnkle, rAnkle) {
        // Center of mass estimation (simplified: midpoint of shoulders + hips)
        const upperCenter = midpoint(
            midpoint(lShoulder, rShoulder),
            midpoint(lHip, rHip)
        );

        // Base of support center
        const baseCenter = midpoint(lAnkle, rAnkle);

        // How far center of mass deviates from base center
        const lateralDeviation = Math.abs(upperCenter.x - baseCenter.x);
        const shoulderWidth = dist(lShoulder, rShoulder);

        const deviationRatio = lateralDeviation / (shoulderWidth + 0.001);

        let score;
        if (deviationRatio < 0.15) {
            score = 100;
        } else if (deviationRatio < 0.3) {
            score = 100 - (deviationRatio - 0.15) * 300;
        } else {
            score = Math.max(0, 55 - (deviationRatio - 0.3) * 200);
        }

        let message, status;
        if (score >= 75) {
            message = "Bon equilibre. Ton poids est bien reparti sur ta base.";
            status = "ok";
        } else if (score >= 45) {
            message = "Equilibre moyen. Recentre ton poids au-dessus de ta base.";
            status = "warning";
        } else {
            message = "Desequilibre ! Tu penches trop d'un cote. Replante-toi sur tes appuis.";
            status = "issue";
        }

        return { score: Math.max(0, Math.min(100, score)), message, status };
    }

    // ========== GUARD RETURN ==========
    function analyzeGuardReturn(lWrist, rWrist, nose, shoulderWidth) {
        // Track wrist positions over time
        wristHistory.push({
            lx: lWrist.x, ly: lWrist.y,
            rx: rWrist.x, ry: rWrist.y,
            ny: nose.y
        });
        if (wristHistory.length > HISTORY_SIZE * 2) wristHistory.shift();

        if (wristHistory.length < 15) {
            return { score: 70, message: "Accumulation de donnees...", status: "ok" };
        }

        // Detect punch = wrist moving away from face rapidly then check if it returns
        let returnsDetected = 0;
        let punchesDetected = 0;

        for (let i = 5; i < wristHistory.length - 5; i++) {
            const prev = wristHistory[i - 5];
            const curr = wristHistory[i];
            const next = wristHistory[i + 5];

            // Check left wrist extension (punch)
            const lExtension = Math.abs(curr.ly - prev.ly) + Math.abs(curr.lx - prev.lx);
            if (lExtension > 0.05) {
                punchesDetected++;
                // Check if hand returns close to original
                const lReturn = Math.abs(next.ly - prev.ly) + Math.abs(next.lx - prev.lx);
                if (lReturn < lExtension * 0.7) {
                    returnsDetected++;
                }
            }

            // Check right wrist
            const rExtension = Math.abs(curr.ry - prev.ry) + Math.abs(curr.rx - prev.rx);
            if (rExtension > 0.05) {
                punchesDetected++;
                const rReturn = Math.abs(next.ry - prev.ry) + Math.abs(next.rx - prev.rx);
                if (rReturn < rExtension * 0.7) {
                    returnsDetected++;
                }
            }
        }

        let score;
        if (punchesDetected === 0) {
            score = 70; // No punches yet
        } else {
            score = Math.min(100, (returnsDetected / punchesDetected) * 100);
        }

        let message, status;
        if (punchesDetected < 3) {
            message = "Lance quelques coups pour evaluer ton retour en garde.";
            status = "ok";
            score = 70;
        } else if (score >= 75) {
            message = "Bon retour en garde apres tes frappes.";
            status = "ok";
        } else if (score >= 45) {
            message = "Retour en garde irregulier. Ramene tes mains apres chaque coup.";
            status = "warning";
        } else {
            message = "Tu ne reviens pas en garde ! Apres chaque frappe, ramene immediatement tes mains.";
            status = "issue";
        }

        return { score: Math.max(0, Math.min(100, score)), message, status };
    }

    // ========== TIPS GENERATION ==========
    function generateTips(scores) {
        const tips = [];

        // Sort by worst score first
        const sorted = Object.entries(scores).sort((a, b) => a[1] - b[1]);

        for (const [key, score] of sorted) {
            if (score >= 80) continue; // No tip needed

            switch (key) {
                case 'guard':
                    if (score < 50) {
                        tips.push({ priority: 'high', text: "<strong>Garde :</strong> Tes mains doivent etre au niveau du menton, paumes vers toi. C'est ta priorite #1." });
                    } else {
                        tips.push({ priority: 'medium', text: "<strong>Garde :</strong> Remonte legerement tes mains. Le dessus de tes poings doit etre au niveau de tes pommettes." });
                    }
                    break;
                case 'stance':
                    tips.push({ priority: score < 50 ? 'high' : 'medium', text: "<strong>Stance :</strong> Pieds a largeur d'epaules, pied avant a 45deg, pied arriere a 90deg. Genoux legerement flechis." });
                    break;
                case 'hips':
                    tips.push({ priority: score < 50 ? 'high' : 'medium', text: "<strong>Hanches :</strong> Chaque coup doit partir de la hanche. Pivote sur ton pied arriere pour generer la rotation." });
                    break;
                case 'elbows':
                    tips.push({ priority: score < 50 ? 'high' : 'medium', text: "<strong>Coudes :</strong> Garde tes coudes colles au corps. Ils protegent tes cotes et ton foie." });
                    break;
                case 'balance':
                    tips.push({ priority: score < 50 ? 'high' : 'medium', text: "<strong>Equilibre :</strong> Repartis ton poids 50/50 ou 60/40 (pied arriere). Ne te penche pas en frappant." });
                    break;
                case 'guardReturn':
                    tips.push({ priority: score < 50 ? 'high' : 'medium', text: "<strong>Retour :</strong> Apres chaque coup, ramene ta main au menton IMMEDIATEMENT. Entraine-toi au ralenti." });
                    break;
            }
        }

        return tips.slice(0, 4); // Max 4 tips
    }

    return { analyze, reset };
})();
