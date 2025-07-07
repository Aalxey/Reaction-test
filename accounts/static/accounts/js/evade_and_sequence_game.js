class EvadeAndSequenceGame {
    constructor() {
        console.log('EvadeAndSequenceGame constructor called');
        this.score = 0;
        this.misses = 0;
        this.gameActive = true;
        this.enemyInRange = false;
        this.gameStarted = false;
        this.gamePaused = false;
        
        // Responsive settings
        this.isMobile = window.innerWidth <= 768;
        this.isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
        
        // Get game elements
        this.gameContainer = document.querySelector('.game-container');
        this.gameArea = document.querySelector('.game-area');
        this.minimap = document.getElementById('minimap');
        this.evadeButton = document.getElementById('evade-button');
        this.startScreen = document.getElementById('start-screen');
        this.gameOverScreen = document.getElementById('game-over-screen');
        this.scoreContainer = document.querySelector('.score-display');
        this.scoreDisplay = document.getElementById('score');
        this.missesDisplay = document.getElementById('misses');
        this.currentSequenceDisplay = document.getElementById('current-sequence');
        this.difficultyIndicator = document.getElementById('difficulty-indicator');
        this.activeCountDisplay = document.getElementById('active-count');
        this.finalScoreDisplay = document.getElementById('final-score');
        this.goToResultBtn = document.getElementById('go-to-result-btn');
        this.preStartOverlay = document.getElementById('pre-start-overlay');
        this.startImmersiveBtn = document.getElementById('start-immersive-btn');
        
        // Minimap elements
        this.playerDot = document.getElementById('player-dot');
        this.enemyDot = document.getElementById('enemy-dot');
        this.playerRange = document.getElementById('player-range');
        
        // Ensure game over screen is hidden initially
        if (this.gameOverScreen) {
            this.gameOverScreen.style.display = 'none';
        }

        // Hide game UI elements by default
        if (this.minimap) this.minimap.style.display = 'none';
        if (this.scoreContainer) this.scoreContainer.style.display = 'none';
        if (this.evadeButton) this.evadeButton.style.display = 'none';
        
        // Game state
        this.enemyPosition = { x: 0, y: 0 };
        this.enemySpeed = this.isMobile ? 0.3 : 0.5; // Slower on mobile for better control
        this.numberSpawnInterval = null;
        this.enemyMoveInterval = null;
        
        // Number sequence tracking
        this.expectedNumbers = [1, 2, 3, 4, 5];
        this.currentSequenceIndex = 0;
        
        // Adaptive difficulty system
        this.difficulty = {
            spawnInterval: 2000, // Start with 2 seconds (faster spawning)
            numberLifetime: 5000, // Numbers stay for 5 seconds (longer lifetime)
            maxNumbersOnScreen: 4, // Start with max 4 numbers
            consecutiveCorrect: 0, // Track consecutive correct clicks
            consecutiveMisses: 0,  // Track consecutive misses
            baseSpawnInterval: 2000,
            minSpawnInterval: 1000, // Fastest spawn rate
            baseLifetime: 5000,
            minLifetime: 2000, // Shortest lifetime
            maxNumbersOnScreenLimit: 6 // Maximum numbers allowed on screen
        };
        
        // Track active numbers to prevent overlapping
        this.activeNumbers = [];
        
        // Responsive adjustments
        this.adjustForScreenSize();
        
        this.init();
        this.setupEventListeners();
        console.log('Constructor completed');
    }
    
    init() {
        console.log('init() called');
        
        // Listen for the immersive start button click
        this.startImmersiveBtn.addEventListener('click', () => this.enterImmersiveModeAndPrepare());
        
        // Handle window resize and orientation changes
        window.addEventListener('resize', () => {
            this.adjustForScreenSize();
            this.updateLayoutForOrientation();
            this.checkInitialOrientation();
            this.setupMobileOptimizations();
        });
        
        // Handle orientation change specifically
        window.addEventListener('orientationchange', () => {
            setTimeout(() => {
                this.adjustForScreenSize();
                this.updateLayoutForOrientation();
                this.checkInitialOrientation();
                this.setupMobileOptimizations();
            }, 100); // Small delay to ensure orientation change is complete
        });
        
        // Initial layout setup
        this.updateLayoutForOrientation();
        console.log('Game initialization completed');
    }

    async enterImmersiveModeAndPrepare() {
        console.log('Entering immersive mode...');
        
        // Hide the button immediately to prevent double clicks
        this.startImmersiveBtn.style.display = 'none';

        try {
            // --- 1. Request Fullscreen ---
            if (document.documentElement.requestFullscreen) {
                await document.documentElement.requestFullscreen();
            } else if (document.documentElement.webkitRequestFullscreen) { /* Safari */
                await document.documentElement.webkitRequestFullscreen();
            } else if (document.documentElement.msRequestFullscreen) { /* IE11 */
                await document.documentElement.msRequestFullscreen();
            }
            console.log('Fullscreen requested successfully.');

            // --- 2. Lock to Landscape Orientation ---
            if (screen.orientation && screen.orientation.lock) {
                await screen.orientation.lock('landscape');
                console.log('Screen orientation locked to landscape.');
            }

            // --- 3. Hide Overlay and Start Countdown ---
            if (this.preStartOverlay) {
                this.preStartOverlay.style.opacity = '0';
                setTimeout(() => {
                    this.preStartOverlay.style.display = 'none';
                }, 500); // Wait for transition
            }

            // --- 4. Show Preparation Screen (Countdown) ---
            console.log('Showing preparation screen...');
            this.showPreparationScreen();

        } catch (error) {
            console.error('Failed to enter immersive mode:', error);
            // If immersive mode fails, hide the overlay and start the game anyway
            if (this.preStartOverlay) {
                this.preStartOverlay.style.display = 'none';
            }
            this.showPreparationScreen();
        }
    }

    showPreparationScreen() {
        // Create countdown overlay directly on game screen
        const countdownOverlay = document.createElement('div');
        countdownOverlay.id = 'countdown-overlay';
        countdownOverlay.style.cssText = `
            position: absolute;
            top: 0; left: 0; width: 100%; height: 100%;
            background-color: rgba(17, 24, 39, 0.95);
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            z-index: 150;
            text-align: center;
            color: #fff;
        `;

        countdownOverlay.innerHTML = `
            <h2 style="font-size: 3rem; margin-bottom: 1rem; color: #facc15;">🎮 Get Ready!</h2>
            <p style="font-size: 1.2rem; margin-bottom: 2rem; color: #a7b3d9; max-width: 500px;">
                The game is about to begin. Focus on the minimap and numbers!
            </p>
            
            <div id="countdown-display" style="font-size: 8rem; font-weight: 900; color: #facc15; margin: 2rem 0; min-height: 10rem; display: flex; align-items: center; justify-content: center; text-shadow: 0 0 30px rgba(250, 204, 21, 0.8);">
                3
            </div>
            
            <div style="background: rgba(30, 41, 59, 0.5); border-radius: 12px; padding: 1.5rem; margin: 1rem 0; border: 1px solid rgba(255, 255, 255, 0.1); max-width: 400px;">
                <h3 style="color: #3b82f6; margin-bottom: 1rem;">🎯 Quick Reminder</h3>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; font-size: 0.9rem;">
                    <div>
                        <p style="margin: 0.3rem 0;"><span style="color: #22c55e;">📊</span> Click numbers 1→2→3→4→5</p>
                        <p style="margin: 0.3rem 0;"><span style="color: #ef4444;">⚡</span> Watch minimap for enemy</p>
                    </div>
                    <div>
                        <p style="margin: 0.3rem 0;"><span style="color: #facc15;">🎯</span> Yellow = next number</p>
                        <p style="margin: 0.3rem 0;"><span style="color: #3b82f6;">🛡️</span> Click EVADE when needed</p>
                    </div>
                </div>
            </div>
            
            <p style="color: #a7b3d9; font-size: 1rem; margin-top: 1rem;">
                Game starts in <span id="countdown-text">3</span> seconds...
            </p>
        `;

        this.gameContainer.appendChild(countdownOverlay);

        // Start countdown
        let countdown = 3;
        const countdownDisplay = document.getElementById('countdown-display');
        const countdownText = document.getElementById('countdown-text');

        const countdownInterval = setInterval(() => {
            countdown--;
            
            if (countdown > 0) {
                countdownDisplay.textContent = countdown;
                countdownText.textContent = countdown;
                
                // Add enhanced pulse animation
                countdownDisplay.style.animation = 'none';
                setTimeout(() => {
                    countdownDisplay.style.animation = 'countdown-pulse 1s ease-in-out infinite, countdown-glow 1s ease-in-out infinite';
                }, 10);
            } else {
                clearInterval(countdownInterval);
                countdownDisplay.textContent = 'GO!';
                countdownDisplay.style.color = '#22c55e';
                countdownDisplay.style.animation = 'go-glow 1s ease-in-out infinite';

                
                // Start game after a short delay
                setTimeout(() => {
                    countdownOverlay.remove();
                    this.startGame();
                }, 1000);
            }
        }, 1000);
    }

    startGame() {
        console.log('startGame() called');
        if (this.gameStarted) {
            console.log('Game already started, returning');
            return;
        }

        // --- Make Game UI Visible ---
        console.log('Showing main game UI elements...');
        if (this.minimap) this.minimap.style.display = 'block';
        if (this.scoreContainer) this.scoreContainer.style.display = 'block';
        if (this.evadeButton) {
            this.evadeButton.style.display = 'block';
            this.evadeButton.disabled = false;
        }
        
        console.log('Setting game state...');
        this.gameStarted = true;
        this.score = 0;
        this.misses = 0;
        this.currentSequenceIndex = 0;
        this.gameActive = true;
        
        // Ensure game over screen is hidden
        this.gameOverScreen.style.display = 'none';
        
        console.log('Resetting UI and starting intervals...');
        this.updateUI();
        this.startNumberSpawning();
        this.startEnemyMovement();
        
        // Initial call to update highlights
        this.updateNumberHighlights();
        
        console.log('Game started successfully');
    }
    
    setupEventListeners() {
        // Evade button
        this.evadeButton.addEventListener('click', () => this.evade());
        
        // Mouse movement for player (optional - could be used for future features)
        this.gameContainer.addEventListener('mousemove', (e) => {
            // Player stays centered, but we track mouse for potential future features
        });
        
        // Go to result button
        this.goToResultBtn.addEventListener('click', () => {
            this.saveScoreAndGoToResult();
        });
        
        // Pause on spacebar or escape key
        document.addEventListener('keydown', (e) => {
            if (e.code === 'Space' || e.code === 'Escape') {
                e.preventDefault();
                if (this.gameStarted && this.gameActive && !this.gamePaused) {
                    this.pauseGame();
                } else if (this.gamePaused) {
                    this.resumeGame();
                }
            }
        });
    }
    
    spawnEnemy() {
        // Spawn enemy at a random edge of the minimap
        const side = Math.floor(Math.random() * 4); // 0: top, 1: right, 2: bottom, 3: left
        
        // Get actual minimap dimensions
        const minimapRect = this.minimap.getBoundingClientRect();
        const minimapWidth = minimapRect.width;
        const minimapHeight = minimapRect.height;
        
        switch(side) {
            case 0: // top
                this.enemyPosition.x = Math.random() * minimapWidth;
                this.enemyPosition.y = 0;
                break;
            case 1: // right
                this.enemyPosition.x = minimapWidth;
                this.enemyPosition.y = Math.random() * minimapHeight;
                break;
            case 2: // bottom
                this.enemyPosition.x = Math.random() * minimapWidth;
                this.enemyPosition.y = minimapHeight;
                break;
            case 3: // left
                this.enemyPosition.x = 0;
                this.enemyPosition.y = Math.random() * minimapHeight;
                break;
        }
        
        this.updateEnemyPosition();
    }
    
    startEnemyMovement() {
        this.enemyMoveInterval = setInterval(() => {
            if (!this.gameActive || this.gamePaused) return;
            
            // Get minimap center (player position)
            const minimapRect = this.minimap.getBoundingClientRect();
            const centerX = minimapRect.width / 2;
            const centerY = minimapRect.height / 2;
            
            const dx = centerX - this.enemyPosition.x;
            const dy = centerY - this.enemyPosition.y;
            const distance = Math.sqrt(dx * dx + dy * dy);
            
            // --- Updated collision logic ---
            // Get radii of player and enemy dots (assume both are 20px diameter by default)
            const playerDot = this.playerDot || { offsetWidth: 20 };
            const enemyDot = this.enemyDot || { offsetWidth: 20 };
            const playerRadius = playerDot.offsetWidth ? playerDot.offsetWidth / 2 : 10;
            const enemyRadius = enemyDot.offsetWidth ? enemyDot.offsetWidth / 2 : 10;
            const collisionDistance = playerRadius + enemyRadius;
            
            if (distance < collisionDistance) {
                this.gameOver('Enemy caught you!');
            }
            
            if (distance > 0) {
                this.enemyPosition.x += (dx / distance) * this.enemySpeed;
                this.enemyPosition.y += (dy / distance) * this.enemySpeed;
            }
            
            this.updateEnemyPosition();
            this.checkEnemyRange();
        }, 16); // ~60 FPS
    }
    
    updateEnemyPosition() {
        this.enemyDot.style.left = this.enemyPosition.x + 'px';
        this.enemyDot.style.top = this.enemyPosition.y + 'px';
    }
    
    checkEnemyRange() {
        // Get minimap center (player position)
        const minimapRect = this.minimap.getBoundingClientRect();
        const centerX = minimapRect.width / 2;
        const centerY = minimapRect.height / 2;
        const rangeRadius = 30; // Detection range radius
        
        const distance = Math.sqrt(
            Math.pow(this.enemyPosition.x - centerX, 2) + 
            Math.pow(this.enemyPosition.y - centerY, 2)
        );
        
        const wasInRange = this.enemyInRange;
        this.enemyInRange = distance <= rangeRadius;
        
        // Update evade button state
        this.evadeButton.disabled = !this.enemyInRange;
        
        // Visual feedback
        if (this.enemyInRange && !wasInRange) {
            this.playerRange.style.borderColor = 'rgba(239, 68, 68, 0.8)';
            this.playerRange.style.animation = 'pulse-warning 1s infinite';
        } else if (!this.enemyInRange && wasInRange) {
            this.playerRange.style.borderColor = 'rgba(60, 130, 246, 0.5)';
            this.playerRange.style.animation = 'none';
        }
    }
    
    evade() {
        if (!this.enemyInRange || !this.gameActive || this.gamePaused) return;
        
        // Teleport enemy back to edge
        this.spawnEnemy();
        
        // Visual feedback
        this.evadeButton.style.transform = 'scale(0.95)';
        setTimeout(() => {
            this.evadeButton.style.transform = 'scale(1)';
        }, 100);
    }
    
    startNumberSpawning() {
        if (this.numberSpawnInterval) {
            clearInterval(this.numberSpawnInterval);
        }
        // Ensure the game area is clear before starting
        this.gameArea.innerHTML = '';
        this.activeNumbers = [];
        this.spawnNumberSet();
    }

    spawnNumberSet() {
        this.currentSequenceIndex = 0;
        for (let i = 1; i <= 5; i++) {
            this.spawnNumber(i);
        }
    }

    spawnNumber(numberValue) {
        if (!this.gameActive || this.gamePaused) {
            return;
        }
        // Avoid re-spawning a number that is somehow still active
        if (this.activeNumbers.some(n => n.value === numberValue)) {
            return;
        }
        const number = document.createElement('div');
        number.className = 'target-number';
        number.textContent = numberValue;
        number.dataset.value = numberValue;
        this.updateNumberHighlight(number);
        const position = this.findNonOverlappingPosition();
        if (!position) {
            setTimeout(() => this.spawnNumber(numberValue), 100);
            return;
        }
        number.style.left = position.x + 'px';
        number.style.top = position.y + 'px';
        number.addEventListener('click', () => this.handleNumberClick(number));
        this.gameArea.appendChild(number);
        this.activeNumbers.push({
            element: number,
            position: position,
            value: numberValue
        });
        this.updateUI();
    }
    
    findNonOverlappingPosition() {
        const maxAttempts = 50;
        let attempts = 0;
        while (attempts < maxAttempts) {
            const position = this.getRandomPosition();
            // Check overlap with other numbers
            const overlaps = this.activeNumbers.some(activeNumber => {
                const distance = Math.sqrt(
                    Math.pow(position.x - activeNumber.position.x, 2) + 
                    Math.pow(position.y - activeNumber.position.y, 2)
                );
                const minDistance = this.isMobile ? 80 : 100;
                return distance < minDistance;
            });
            // Check overlap with minimap and evade button
            if (!overlaps && !this.overlapsWithUI(position)) {
                return position;
            }
            attempts++;
        }
        return null;
    }

    overlapsWithUI(position) {
        // Minimap
        if (this.minimap) {
            const rect = this.minimap.getBoundingClientRect();
            if (this.positionOverlapsRect(position, rect, 70)) return true;
        }
        // Evade button
        if (this.evadeButton) {
            const rect = this.evadeButton.getBoundingClientRect();
            if (this.positionOverlapsRect(position, rect, 70)) return true;
        }
        return false;
    }

    positionOverlapsRect(position, rect, size) {
        // size: diameter of number
        const numberLeft = position.x;
        const numberRight = position.x + size;
        const numberTop = position.y;
        const numberBottom = position.y + size;
        const rectLeft = rect.left - this.gameArea.getBoundingClientRect().left;
        const rectRight = rect.right - this.gameArea.getBoundingClientRect().left;
        const rectTop = rect.top - this.gameArea.getBoundingClientRect().top;
        const rectBottom = rect.bottom - this.gameArea.getBoundingClientRect().top;
        return (
            numberRight > rectLeft &&
            numberLeft < rectRight &&
            numberBottom > rectTop &&
            numberTop < rectBottom
        );
    }

    getRandomPosition() {
        console.log('getRandomPosition() called');
        
        // Get game area dimensions (relative to its parent)
        const gameArea = this.gameArea;
        const gameAreaWidth = gameArea.offsetWidth;
        const gameAreaHeight = gameArea.offsetHeight;
        
        console.log('Game area dimensions:', gameAreaWidth, 'x', gameAreaHeight);
        
        // Adjust target size based on screen
        const targetSize = this.isMobile ? 55 : 70;
        
        // Use responsive padding based on screen size
        let padding;
        if (window.innerWidth <= 480) {
            padding = 60; // Very small screens
        } else if (window.innerWidth <= 768) {
            padding = 80; // Mobile screens
        } else {
            padding = 120; // Desktop screens
        }
        
        console.log('Padding:', padding, 'Target size:', targetSize);
        
        // Calculate safe spawning area (inside the padding)
        const safeWidth = gameAreaWidth - 2 * padding;
        const safeHeight = gameAreaHeight - 2 * padding;
        
        console.log('Safe area dimensions:', safeWidth, 'x', safeHeight);
        
        // Ensure we have valid dimensions
        if (safeWidth <= targetSize || safeHeight <= targetSize) {
            console.log('Safe area too small, using fallback position');
            // Fallback to center if safe area is too small
            return {
                x: gameAreaWidth / 2 - targetSize / 2,
                y: gameAreaHeight / 2 - targetSize / 2
            };
        }
        
        // Generate random position within safe area
        const x = padding + Math.random() * (safeWidth - targetSize);
        const y = padding + Math.random() * (safeHeight - targetSize);
        
        console.log('Generated position:', { x, y });
        
        return { x, y };
    }
    
    updateNumberHighlight(numberElement) {
        const value = parseInt(numberElement.dataset.value);
        if (value === this.expectedNumbers[this.currentSequenceIndex]) {
            numberElement.style.border = '4px solid #facc15';
            numberElement.style.boxShadow = '0 0 20px rgba(250, 204, 21, 0.8)';
        } else {
            numberElement.style.border = '4px solid rgba(255,255,255,0.5)';
            numberElement.style.boxShadow = '0 0 20px rgba(255,255,255,0.5)';
        }
    }

    updateAllNumberHighlights() {
        this.activeNumbers.forEach(activeNumber => {
            this.updateNumberHighlight(activeNumber.element);
        });
    }

    handleNumberClick(number) {
        if (this.gamePaused) return;
        const clickedValue = parseInt(number.dataset.value);
        if (number.style.opacity === '0') return;
        if (clickedValue === this.expectedNumbers[this.currentSequenceIndex]) {
            this.score += 10;
            this.currentSequenceIndex++;
            this.difficulty.consecutiveCorrect++;
            this.difficulty.consecutiveMisses = 0;
            number.style.transform = 'scale(0)';
            number.style.opacity = '0';
            this.removeFromActiveNumbers(number);
            setTimeout(() => {
                if (number.parentNode) number.remove();
                // Do not respawn the clicked number
                if (this.activeNumbers.length === 0) {
                    this.score += 50;
                    this.spawnNumberSet();
                }
            }, 300);
            this.updateAllNumberHighlights();
        } else {
            this.handleNumberMiss(number);
        }
        this.adjustDifficulty();
        this.updateUI();
    }

    handleNumberMiss(number) {
        const missedValue = parseInt(number.dataset.value);
        this.misses++;
        this.gameContainer.classList.add('shake');
        this.difficulty.consecutiveMisses++;
        this.difficulty.consecutiveCorrect = 0;
        number.style.opacity = '0';
        this.removeFromActiveNumbers(number);
        setTimeout(() => {
            if (number.parentNode) number.remove();
            this.gameContainer.classList.remove('shake');
            // Do not respawn the missed number
            if (this.activeNumbers.length === 0) {
                this.spawnNumberSet();
            }
        }, 300);
        this.adjustDifficulty();
        this.updateUI();
        if (this.misses >= 3) {
            this.gameOver('Too many misses!');
        }
    }

    removeFromActiveNumbers(number) {
        const index = this.activeNumbers.findIndex(active => active.element === number);
        if (index !== -1) {
            this.activeNumbers.splice(index, 1);
        }
    }
    
    updateUI() {
        this.scoreDisplay.textContent = this.score;
        this.missesDisplay.textContent = 'Misses: ' + this.misses + '/3';
        
        const currentExpected = this.expectedNumbers[this.currentSequenceIndex];
        if (this.currentSequenceDisplay) {
            this.currentSequenceDisplay.textContent = 'Next: ' + currentExpected;
        }
        
        if (this.difficultyIndicator) {
            const difficultyLevel = this.calculateDifficultyLevel();
            this.difficultyIndicator.textContent = 'Speed: ' + difficultyLevel;
        }
        
        if (this.activeCountDisplay) {
            this.activeCountDisplay.textContent = 'Numbers: ' + this.activeNumbers.length + '/' + 5;
        }
    }
    
    calculateDifficultyLevel() {
        const spawnRate = this.difficulty.baseSpawnInterval - this.difficulty.spawnInterval;
        const maxSpawnRate = this.difficulty.baseSpawnInterval - this.difficulty.minSpawnInterval;
        const percentage = (spawnRate / maxSpawnRate) * 100;
        
        if (percentage < 20) return 'Easy';
        if (percentage < 40) return 'Normal';
        if (percentage < 60) return 'Hard';
        if (percentage < 80) return 'Expert';
        return 'Master';
    }
    
    gameOver(reason) {
        if (!this.gameActive) return; // Prevent multiple calls
        this.gameActive = false;
        this.gameContainer.classList.add('shake');
        
        // Clear intervals
        if (this.enemyMoveInterval) clearInterval(this.enemyMoveInterval);
        if (this.numberSpawnInterval) clearInterval(this.numberSpawnInterval);
        
        // Remove all numbers from game area and clear active numbers
        this.gameArea.querySelectorAll('.target-number').forEach(num => num.remove());
        this.activeNumbers = [];
        
        // Show game over screen
        this.finalScoreDisplay.textContent = this.score;
        this.gameOverScreen.style.display = 'flex';
        
        console.log('Game Over:', reason);
    }
    
    saveScore(redirectToResult = false) {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        
        fetch('/accounts/save-evade-and-sequence-score/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify({
                score: this.score,
                misses: this.misses
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                if (redirectToResult && data.result_id) {
                    window.location.href = `/accounts/evade-and-sequence-result/${data.result_id}/`;
                } else {
                    window.location.href = '/accounts/dashboard/';
                }
            } else {
                alert('Failed to save score: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error saving score:', error);
            alert('Failed to save score. Please try again.');
        });
    }
    
    saveScoreAndGoToResult() {
        this.saveScore(true);
    }
    
    adjustForScreenSize() {
        // Update responsive settings
        this.isMobile = window.innerWidth <= 768;
        this.enemySpeed = this.isMobile ? 0.3 : 0.5;
        
        // Adjust minimap size based on screen
        const minimapSize = this.isMobile ? (window.innerWidth <= 480 ? 100 : 120) : 200;
        this.minimapSize = minimapSize;
        
        // Adjust spawn intervals for mobile
        if (this.numberSpawnInterval) {
            clearInterval(this.numberSpawnInterval);
            this.startNumberSpawning();
        }
    }
    
    updateLayoutForOrientation() {
        const isLandscape = window.innerWidth > window.innerHeight;
        const gameContainer = this.gameContainer;
        
        if (isLandscape) {
            // Landscape mode - horizontal layout
            gameContainer.style.flexDirection = 'row';
            gameContainer.style.alignItems = 'center';
            gameContainer.style.justifyContent = 'space-between';
            
            // Ensure minimap is top-left
            this.minimap.style.position = 'absolute';
            this.minimap.style.top = '0.5rem';
            this.minimap.style.left = '0.5rem';
            this.minimap.style.zIndex = '10';
            
            // Ensure evade button is bottom-right
            this.evadeButton.style.position = 'absolute';
            this.evadeButton.style.bottom = '0.5rem';
            this.evadeButton.style.right = '0.5rem';
            this.evadeButton.style.zIndex = '10';
            
            // Ensure score display is top-right
            const scoreDisplay = document.querySelector('.score-display');
            if (scoreDisplay) {
                scoreDisplay.style.position = 'absolute';
                scoreDisplay.style.top = '0.5rem';
                scoreDisplay.style.right = '0.5rem';
                scoreDisplay.style.zIndex = '10';
            }
            
            console.log('Layout updated for LANDSCAPE mode');
        } else {
            // Portrait mode - vertical layout
            gameContainer.style.flexDirection = 'column';
            
            console.log('Layout updated for PORTRAIT mode');
        }
    }

    checkInitialOrientation() {
        const rotateMessage = document.getElementById('rotate-device-message');
        if (!rotateMessage) return;

        const isPortrait = window.innerHeight > window.innerWidth;
        const isMobile = window.innerWidth <= 768;

        if (isPortrait && isMobile) {
            rotateMessage.style.display = 'block';
        } else {
            rotateMessage.style.display = 'none';
        }
    }
    
    adjustDifficulty() {
        // Adjust based on consecutive correct clicks (make it harder)
        if (this.difficulty.consecutiveCorrect >= 3) {
            this.difficulty.spawnInterval = Math.max(
                this.difficulty.minSpawnInterval,
                this.difficulty.spawnInterval - 200
            );
            
            this.difficulty.consecutiveCorrect = 0;
        }
        
        // Adjust based on consecutive misses (make it easier)
        if (this.difficulty.consecutiveMisses >= 2) {
            this.difficulty.spawnInterval = Math.min(
                this.difficulty.baseSpawnInterval,
                this.difficulty.spawnInterval + 300
            );
            
            this.difficulty.consecutiveMisses = 0;
        }

        // The spawn interval is no longer used for numbers, but could be used
        // for other game mechanics in the future (e.g., power-ups)
    }
    
    pauseGame() {
        if (!this.gameActive || this.gamePaused) return;
        
        this.gamePaused = true;
        
        // Create pause overlay
        const pauseOverlay = document.createElement('div');
        pauseOverlay.id = 'pause-overlay';
        pauseOverlay.style.cssText = `
            position: absolute;
            top: 0; left: 0; width: 100%; height: 100%;
            background-color: rgba(0, 0, 0, 0.8);
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            z-index: 200;
            text-align: center;
            color: #fff;
        `;
        
        pauseOverlay.innerHTML = `
            <h2 style="font-size: 3rem; margin-bottom: 1rem; color: #facc15;">⏸️ Game Paused</h2>
            <p style="font-size: 1.2rem; margin-bottom: 2rem; color: #a7b3d9;">
                Take a moment to breathe and refocus.
            </p>
            <div style="background: rgba(30, 41, 59, 0.5); border-radius: 12px; padding: 1.5rem; margin: 1rem 0; border: 1px solid rgba(255, 255, 255, 0.1); max-width: 400px;">
                <h3 style="color: #3b82f6; margin-bottom: 1rem;">🎯 Current Status</h3>
                <p style="color: #a7b3d9; margin: 0.5rem 0;">Score: <span style="color: #fff; font-weight: 600;">${this.score}</span></p>
                <p style="color: #a7b3d9; margin: 0.5rem 0;">Misses: <span style="color: #fff; font-weight: 600;">${this.misses}/3</span></p>
                <p style="color: #a7b3d9; margin: 0.5rem 0;">Next Number: <span style="color: #facc15; font-weight: 600;">${this.expectedNumbers[this.currentSequenceIndex]}</span></p>
            </div>
            <button id="resume-btn" style="font-size: 1.2rem; padding: 1rem 2rem; background: linear-gradient(135deg, #22c55e, #16a34a); border: none; color: white; font-weight: 700; border-radius: 12px; cursor: pointer; margin: 1rem; transition: all 0.3s ease;">
                ▶️ Resume Game
            </button>
            <p style="color: #a7b3d9; font-size: 0.9rem; margin-top: 1rem;">
                Press SPACE or ESC to resume
            </p>
        `;
        
        this.gameContainer.appendChild(pauseOverlay);
        
        // Add resume button listener
        document.getElementById('resume-btn').addEventListener('click', () => {
            this.resumeGame();
        });
    }
    
    resumeGame() {
        if (!this.gamePaused) return;
        
        this.gamePaused = false;
        
        // Remove pause overlay
        const pauseOverlay = document.getElementById('pause-overlay');
        if (pauseOverlay) {
            pauseOverlay.remove();
        }
    }

    setupMobileOptimizations() {
        // Check if we're on mobile
        const isMobile = window.innerWidth <= 768;
        const mobileInstruction = document.getElementById('mobile-instruction');
        
        if (isMobile) {
            console.log('Mobile device detected, applying optimizations');
            
            // Show mobile instruction if it exists
            if (mobileInstruction) {
                mobileInstruction.style.display = 'block';
            }
        } else {
            // Hide mobile instruction on desktop
            if (mobileInstruction) {
                mobileInstruction.style.display = 'none';
            }
        }
    }
}

// Initialize game when page loads
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing Evade & Sequence game...');
    try {
        const game = new EvadeAndSequenceGame();
        console.log('Game initialized successfully');
    } catch (error) {
        console.error('Failed to initialize game:', error);
    }
});