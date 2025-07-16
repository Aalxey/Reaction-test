console.log('Aim Trainer JS loaded');
// Aim Trainer Game JS - Advanced Target Behavior

document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const crosshair = document.getElementById('crosshair');
    const joystickThumb = document.getElementById('joystick-thumb');
    const fireBtn = document.getElementById('fire-btn');
    const target = document.getElementById('target');
    const hpBar = document.getElementById('hp-bar');
    const destroyedMsg = document.getElementById('destroyed-message');

    // Sensitivity (read from localStorage, default 1, but allow live update)
    let sensitivity = 1;
    if (window._aimTrainerSensitivity !== undefined) {
        sensitivity = window._aimTrainerSensitivity;
    } else {
        const stored = localStorage.getItem('aim_trainer_sensitivity');
        if (stored) {
            sensitivity = parseFloat(stored);
        }
        window._aimTrainerSensitivity = sensitivity;
    }
    window.setAimTrainerSensitivity = function(val) {
        sensitivity = parseFloat(val);
        window._aimTrainerSensitivity = sensitivity;
    }

    // Game state
    let crosshairPos = { x: 0.5, y: 0.6 };
    let crosshairVel = { x: 0, y: 0 };
    let targetPos = { x: 0.5, y: 0.09 };
    let targetHP = 100;
    const maxHP = 100;
    let joystickActive = false;
    let joystickStart = { x: 0, y: 0 };
    let joystickDir = { x: 0, y: 0 };
    // Target movement
    let targetMoving = false;
    let targetVelocity = { x: 0, y: 0 };
    let targetDirectionChangeTimer = 0;
    let regenInterval = null;

    // Anti-rapid-fire state
    let rapidFireMode = false;
    let rapidFireTimeout = null;
    let fireTimestamps = [];

    function updatePositions() {
        crosshair.style.left = (crosshairPos.x * 100) + '%';
        crosshair.style.top = (crosshairPos.y * 100) + '%';
        target.parentElement.style.left = (targetPos.x * 100) + '%';
        target.parentElement.style.top = (targetPos.y * 100) + '%';
    }
    function updateHPBar() {
        hpBar.style.width = targetHP + '%';
    }
    function resetGame() {
        crosshairPos = { x: 0.5, y: 0.6 };
        crosshairVel = { x: 0, y: 0 };
        // Place target at a random position outside the avoidance radius from the crosshair
        let tx, ty;
        do {
            tx = 0.1 + 0.8 * Math.random();
            ty = 0.05 + 0.4 * Math.random(); // keep in upper half
        } while (Math.hypot(tx - crosshairPos.x, ty - crosshairPos.y) < AVOID_RADIUS);
        targetPos = { x: tx, y: ty };
        targetHP = 100;
        destroyedMsg.style.display = 'none';
        target.style.display = 'block';
        targetMoving = false;
        targetVelocity = { x: 0, y: 0 };
        targetDirectionChangeTimer = 0;
        stopHPRegen();
        updatePositions();
        updateHPBar();
    }

    // Add timer element to the DOM
    let timerElem = document.createElement('div');
    timerElem.id = 'game-timer';
    timerElem.style.position = 'fixed';
    timerElem.style.top = '24px';
    timerElem.style.left = '50%';
    timerElem.style.transform = 'translateX(-50%)';
    timerElem.style.fontSize = '2.2rem';
    timerElem.style.color = '#fff';
    timerElem.style.fontWeight = 'bold';
    timerElem.style.zIndex = '1000';
    timerElem.style.textShadow = '0 2px 8px #000';
    document.body.appendChild(timerElem);

    let timerInterval = null;
    let timeLeft = 60; // seconds
    let hits = 0;
    let shots = 0;

    function updateTimerDisplay() {
        let min = Math.floor(timeLeft / 60);
        let sec = timeLeft % 60;
        timerElem.textContent = `${min}:${sec.toString().padStart(2, '0')}`;
    }

    // Remove Save and Start Game button overlay and related logic
    // Show timer immediately
    timerElem.style.display = 'block';
    // Do not start timer or enemy movement on page load
    // targetMoving = true; // Remove this from page load
    // startTimer(); // Remove this from page load

    // Start timer and enemy movement when Save Sensitivity is clicked
    const saveBtn = document.getElementById('save-sensitivity-btn');
    if (saveBtn) {
        saveBtn.addEventListener('click', function() {
            startTimer();
            targetMoving = true;
        });
    }

    // Override startTimer to also enable enemy movement
    function startTimer() {
        timeLeft = 60;
        updateTimerDisplay();
        if (timerInterval) clearInterval(timerInterval);
        timerInterval = setInterval(() => {
            timeLeft--;
            updateTimerDisplay();
            if (timeLeft <= 0) {
                clearInterval(timerInterval);
                timerElem.textContent = "Time's up!";
                targetMoving = false;
                endGameAndShowResult();
            }
        }, 1000);
        targetMoving = true;
    }

    // Start game on button click
    // startBtn.addEventListener('click', function() {
    //     startBtnOverlay.style.display = 'none';
    //     timerElem.style.display = 'block';
    //     startTimer();
    //     gameStarted = true;
    // });

    // Prevent enemy from moving before game starts
    // targetMoving = false; // This line is now handled by the new logic

    // Joystick logic
    joystickThumb.addEventListener('mousedown', startJoystick);
    joystickThumb.addEventListener('touchstart', startJoystick);
    document.addEventListener('mousemove', moveJoystick);
    document.addEventListener('touchmove', moveJoystick);
    document.addEventListener('mouseup', endJoystick);
    document.addEventListener('touchend', endJoystick);

    function startJoystick(e) {
        joystickActive = true;
        const evt = e.touches ? e.touches[0] : e;
        joystickStart = { x: evt.clientX, y: evt.clientY };
        joystickDir = { x: 0, y: 0 };
        e.preventDefault();
    }
    function moveJoystick(e) {
        if (!joystickActive) return;
        const evt = e.touches ? e.touches[0] : e;
        const dx = evt.clientX - joystickStart.x;
        const dy = evt.clientY - joystickStart.y;
        const maxDist = 50;
        let nx = Math.max(-1, Math.min(1, dx / maxDist));
        let ny = Math.max(-1, Math.min(1, dy / maxDist));
        joystickDir = { x: nx, y: ny };
        e.preventDefault();
    }
    function endJoystick(e) {
        joystickActive = false;
        joystickDir = { x: 0, y: 0 };
    }

    // Smooth crosshair movement
    function animateCrosshair() {
        const baseSpeed = 0.012;
        if (joystickActive || joystickDir.x !== 0 || joystickDir.y !== 0) {
            crosshairVel.x = joystickDir.x * baseSpeed * sensitivity;
            crosshairVel.y = joystickDir.y * baseSpeed * sensitivity;
        } else {
            crosshairVel.x = 0;
            crosshairVel.y = 0;
        }
        crosshairPos.x = Math.max(0, Math.min(1, crosshairPos.x + crosshairVel.x));
        crosshairPos.y = Math.max(0, Math.min(1, crosshairPos.y + crosshairVel.y));
        updatePositions();
        requestAnimationFrame(animateCrosshair);
    }
    animateCrosshair();

    // Advanced Target Movement
    // No-go zones for joystick and fire button (bottom corners)
    const NO_GO_MARGIN_X = 0.18; // 18% from left/right
    const NO_GO_MARGIN_Y = 0.18; // 18% from bottom
    const HIT_RADIUS = 0.15;
    const AVOID_RADIUS = 0.18; // Must be > HIT_RADIUS
    function isInNoGoZone(x, y) {
        // Joystick: bottom-left
        if (x < NO_GO_MARGIN_X && y > 1 - NO_GO_MARGIN_Y) return true;
        // Fire button: bottom-right
        if (x > 1 - NO_GO_MARGIN_X && y > 1 - NO_GO_MARGIN_Y) return true;
        return false;
    }

    // Helper: get current speed and randomness based on HP and rapid fire
    function getTargetMovementParams() {
        let speed = 0.004;
        let randomness = Math.PI / 8;
        if (rapidFireMode) {
            speed = 0.004 * 1.5 * 1.7 * 1.15 * 1.5; // max speed multiplier
            randomness = Math.PI; // max randomness
        } else {
            if (targetHP < 50) {
                speed *= 1.5;
                randomness = Math.PI / 5;
            }
            if (targetHP < 25) {
                speed *= 1.7;
                randomness = Math.PI / 3;
            }
            if (targetHP < 15) {
                speed *= 1.15;
                randomness = Math.PI / 2;
            }
        }
        return { speed, randomness };
    }

    // Helper: always move away from crosshair, never toward
    function setVelocityAwayFromCrosshair(offsetRadians = Math.PI / 6) { // ±30°
        const dx = targetPos.x - crosshairPos.x;
        const dy = targetPos.y - crosshairPos.y;
        let angle = Math.atan2(dy, dx);
        // Add small random offset (±offsetRadians)
        angle += (Math.random() - 0.5) * 2 * offsetRadians;
        let { speed } = getTargetMovementParams();
        targetVelocity = { x: Math.cos(angle) * speed, y: Math.sin(angle) * speed };
    }

    function randomizeTargetDirection() {
        // Always move away from crosshair, never toward
        setVelocityAwayFromCrosshair();
    }

    function moveTarget() {
        if (!targetMoving || targetHP <= 0) return;
        targetDirectionChangeTimer--;
        const currDist = Math.hypot(targetPos.x - crosshairPos.x, targetPos.y - crosshairPos.y);
        let forceMoveOutOfNoGo = false;
        // Check if currently in a no-go zone
        if (isInNoGoZone(targetPos.x, targetPos.y)) {
            forceMoveOutOfNoGo = true;
        }
        // Movement logic
        if (forceMoveOutOfNoGo) {
            // Move out of no-go zone: pick direction toward center
            let angle = Math.atan2(0.5 - targetPos.y, 0.5 - targetPos.x);
            let { speed } = getTargetMovementParams();
            targetVelocity = { x: Math.cos(angle) * speed, y: Math.sin(angle) * speed };
        } else if (currDist < AVOID_RADIUS) {
            // Strictly move away from crosshair
            setVelocityAwayFromCrosshair(0); // no randomness
        } else if (rapidFireMode) {
            setVelocityAwayFromCrosshair(0); // no randomness in rapid fire
        } else if (targetDirectionChangeTimer <= 0) {
            // Random movement when outside avoidance radius
            const { speed, randomness } = getTargetMovementParams();
            let currentAngle = Math.atan2(targetVelocity.y, targetVelocity.x);
            let newAngle = currentAngle + (Math.random() - 0.5) * 2 * randomness;
            targetVelocity = { x: Math.cos(newAngle) * speed, y: Math.sin(newAngle) * speed };
            let minFrames = 20, maxFrames = 60;
            if (targetHP < 50) { minFrames = 10; maxFrames = 40; }
            if (targetHP < 25) { minFrames = 5; maxFrames = 25; }
            if (targetHP < 15) { minFrames = 3; maxFrames = 15; }
            targetDirectionChangeTimer = Math.floor(Math.random() * (maxFrames - minFrames) + minFrames);
        }
        let nextX = targetPos.x + targetVelocity.x;
        let nextY = targetPos.y + targetVelocity.y;
        // Bounce off all four edges
        if (nextX < 0.05 || nextX > 0.95) targetVelocity.x *= -1;
        if (nextY < 0.05 || nextY > 0.95) targetVelocity.y *= -1;
        // Prevent entering no-go zones (bottom corners)
        if (isInNoGoZone(nextX, nextY)) {
            // Move toward center if about to enter no-go zone
            let angle = Math.atan2(0.5 - targetPos.y, 0.5 - targetPos.x);
            let { speed } = getTargetMovementParams();
            targetVelocity = { x: Math.cos(angle) * speed, y: Math.sin(angle) * speed };
            nextX = targetPos.x + targetVelocity.x;
            nextY = targetPos.y + targetVelocity.y;
        }
        // Prevent moving closer to crosshair
        const nextDist = Math.hypot(nextX - crosshairPos.x, nextY - crosshairPos.y);
        if (nextDist < currDist && currDist < AVOID_RADIUS) {
            // Only enforce this if already inside avoidance radius
            setVelocityAwayFromCrosshair(0);
            nextX = targetPos.x + targetVelocity.x;
            nextY = targetPos.y + targetVelocity.y;
        }
        targetPos.x = Math.max(0.05, Math.min(0.95, nextX));
        targetPos.y = Math.max(0.05, Math.min(0.95, nextY));
        updatePositions();
    }
    setInterval(moveTarget, 16);

    // HP Regeneration logic
    function startHPRegen() {
        if (regenInterval) return;
        regenInterval = setInterval(() => {
            if (rapidFireMode) {
                if (targetHP > 0 && targetHP < 100) {
                    targetHP = Math.min(100, targetHP + maxHP * 0.01); // regen up to 100%
                    updateHPBar();
                }
                if (targetHP >= 100 || targetHP <= 0) {
                    stopHPRegen();
                }
            } else if (targetHP > 0 && targetHP < 25 && targetHP < 15) {
                // Only regen up to 25% if HP < 15% and not in rapid fire mode
                targetHP = Math.min(25, targetHP + maxHP * 0.01);
                updateHPBar();
                if (targetHP >= 25 || targetHP <= 0) {
                    stopHPRegen();
                }
            } else {
                stopHPRegen();
            }
        }, 1000);
    }
    function stopHPRegen() {
        if (regenInterval) {
            clearInterval(regenInterval);
            regenInterval = null;
        }
    }

    // Rapid fire detection
    function detectRapidFire() {
        const now = Date.now();
        fireTimestamps.push(now);
        // Only keep last 5 timestamps
        if (fireTimestamps.length > 5) fireTimestamps.shift();
        // If 3 or more shots in 500ms, trigger rapid fire mode
        if (fireTimestamps.length >= 3 && (fireTimestamps[fireTimestamps.length-1] - fireTimestamps[fireTimestamps.length-3]) < 500) {
            if (!rapidFireMode) {
                rapidFireMode = true;
                startHPRegen();
                if (rapidFireTimeout) clearTimeout(rapidFireTimeout);
                rapidFireTimeout = setTimeout(() => {
                    rapidFireMode = false;
                }, 2000);
            } else {
                // Extend rapid fire mode
                if (rapidFireTimeout) clearTimeout(rapidFireTimeout);
                rapidFireTimeout = setTimeout(() => {
                    rapidFireMode = false;
                }, 2000);
            }
        }
    }

    // Fire button logic
    fireBtn.addEventListener('click', function() {
        if (destroyedMsg.style.display === 'block') return;
        shots++;
        detectRapidFire();
        const dist = Math.hypot(crosshairPos.x - targetPos.x, crosshairPos.y - targetPos.y);
        if (dist < HIT_RADIUS) {
            hits++;
            if (rapidFireMode) {
                // Don't allow HP to drop below 15%
                if (targetHP > 15) {
                    targetHP -= 20;
                    if (targetHP < 15) targetHP = 15;
                }
            } else {
                targetHP -= 20;
            }
            if (!targetMoving && targetHP > 0) {
                targetMoving = true;
                setVelocityAwayFromCrosshair();
                targetDirectionChangeTimer = 0;
            }
            if (targetHP <= 0) {
                targetHP = 0;
                destroyedMsg.style.display = 'block';
                target.style.display = 'none';
                targetMoving = false;
                stopHPRegen();
                rapidFireMode = false;
            }
            updateHPBar();
        }
    });

    // Watch HP for regen and speed changes
    setInterval(() => {
        if (rapidFireMode) {
            startHPRegen();
        } else if (targetHP > 0 && targetHP < 15) {
            startHPRegen();
        } else {
            stopHPRegen();
        }
    }, 500);

    // Init
    resetGame();

    function ensureTimerVisible() {
        timerElem.style.display = 'block';
        timerElem.style.position = 'fixed';
        timerElem.style.top = '24px';
        timerElem.style.left = '50%';
        timerElem.style.transform = 'translateX(-50%)';
        timerElem.style.fontSize = '2.2rem';
        timerElem.style.color = '#fff';
        timerElem.style.fontWeight = 'bold';
        timerElem.style.zIndex = '1000';
        timerElem.style.textShadow = '0 2px 8px #000';
        // Move timer into fullscreen element if in fullscreen
        let fsElem = document.fullscreenElement;
        if (fsElem && timerElem.parentElement !== fsElem) {
            fsElem.appendChild(timerElem);
        } else if (!fsElem && timerElem.parentElement !== document.body) {
            document.body.appendChild(timerElem);
        }
    }
    // Ensure timer is visible on fullscreen and orientation change
    document.addEventListener('fullscreenchange', ensureTimerVisible);
    window.addEventListener('orientationchange', ensureTimerVisible);
    // Also call once on load
    ensureTimerVisible();

    function endGameAndShowResult() {
        const accuracy = shots > 0 ? Math.round((hits / shots) * 100) : 0;
        // Save result to backend, then redirect
        fetch('/accounts/save-aim-trainer-result/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || ''
            },
            body: `hits=${hits}&shots=${shots}&accuracy=${accuracy}`
        }).then(() => {
            window.location.href = `/accounts/aim_trainer_result/?hits=${hits}&shots=${shots}&accuracy=${accuracy}`;
        }).catch(() => {
            window.location.href = `/accounts/aim_trainer_result/?hits=${hits}&shots=${shots}&accuracy=${accuracy}`;
        });
    }
}); 