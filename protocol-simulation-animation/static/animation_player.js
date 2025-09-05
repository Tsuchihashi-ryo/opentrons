document.addEventListener('DOMContentLoaded', () => {
    // --- UI Elements ---
    const uploadForm = document.getElementById('upload-form');
    const statusDiv = document.getElementById('status');
    const playbackControls = document.getElementById('playback-controls');
    const canvas = document.getElementById('player-canvas');
    const ctx = canvas.getContext('2d');
    const commandTextDiv = document.getElementById('command-text');
    const frameSlider = document.getElementById('frame-slider');
    const frameCounter = document.getElementById('frame-counter');
    const playPauseBtn = document.getElementById('play-pause-btn');

    // --- State ---
    let runlog = [];
    let labwareDefinitions = {}; // Cache for fetched labware definitions
    let labwareLocations = {}; // { labwareId: {-..props}}
    let liquidState = {}; // { labwareId: { wellName: { liquid: volume } } }
    let animationTimer = null;
    let currentFrame = 0;

    // --- Event Listeners ---
    uploadForm.addEventListener('submit', handleFormSubmit);
    frameSlider.addEventListener('input', (e) => drawFrame(parseInt(e.target.value, 10)));
    playPauseBtn.addEventListener('click', togglePlayPause);

    // --- Main Logic ---
    async function handleFormSubmit(event) {
        event.preventDefault();
        resetPlayer();
        statusDiv.textContent = 'Uploading and simulating...';

        const formData = new FormData(uploadForm);

        try {
            const response = await fetch('/animate', { method: 'POST', body: formData });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
            }
            runlog = await response.json();
            statusDiv.textContent = `Simulation successful! Processing ${runlog.length} commands.`;

            await setupSimulationState();
            setupPlayerUI();
            drawFrame(0);

        } catch (error) {
            console.error('Error:', error);
            statusDiv.textContent = `Error: ${error.message}`;
        }
    }

    function resetPlayer() {
        if (animationTimer) clearInterval(animationTimer);
        runlog = [];
        labwareDefinitions = {};
        labwareLocations = {};
        liquidState = {};
        currentFrame = 0;
        playbackControls.style.display = 'none';
        statusDiv.textContent = 'Ready';
        commandTextDiv.textContent = '...';
    }

    async function setupSimulationState() {
        // Find all unique labware and their locations from the runlog
        for (const command of runlog) {
            const text = command.payload.text || '';
            const info = getLabwareAndWellInfo(text);
            if (info) {
                const { labware, slot, well } = info;
                const labwareId = `${labware}_${slot}`;
                if (!labwareLocations[labwareId]) {
                    const loadName = guessLoadName(labware);
                    labwareLocations[labwareId] = { loadName, slot, type: labware };
                }
            }
        }

        // Fetch all labware definitions
        for (const [id, loc] of Object.entries(labwareLocations)) {
            if (loc.loadName) {
                labwareDefinitions[loc.loadName] = await fetchLabwareDefinition(loc.loadName);
            }
        }

        // Initialize liquid state
        // TODO: A more robust way to parse initial liquid state is needed.
        // For now, we assume everything starts empty.
    }

    function setupPlayerUI() {
        if (runlog && runlog.length > 0) {
            playbackControls.style.display = 'block';
            frameSlider.max = runlog.length - 1;
            frameSlider.value = 0;
            frameCounter.textContent = `1 / ${runlog.length}`;
        }
    }

    function drawFrame(frameIndex) {
        if (frameIndex < 0 || frameIndex >= runlog.length) return;
        currentFrame = frameIndex;

        const command = runlog[frameIndex];
        commandTextDiv.textContent = command.payload.text || 'No text';
        frameCounter.textContent = `${frameIndex + 1} / ${runlog.length}`;
        frameSlider.value = frameIndex;

        // --- Main Canvas Drawing ---
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = '#eef2f6';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // This is a simplified drawing logic. A real one would be more complex.
        const slotPositions = { '1': [50, 50], '2': [200, 50], '3': [350, 50], '12': [350, 350] };

        // Draw labware outlines
        for (const [id, loc] of Object.entries(labwareLocations)) {
            const def = labwareDefinitions[loc.loadName];
            if (!def) continue;

            const [x, y] = slotPositions[loc.slot] || [50, 200];
            ctx.strokeStyle = 'gray';
            ctx.lineWidth = 1;
            ctx.strokeRect(x, y, def.dimensions.xDimension, def.dimensions.yDimension);
            ctx.font = '10px sans-serif';
            ctx.fillStyle = 'black';
            ctx.textAlign = 'center';
            ctx.fillText(loc.type, x + def.dimensions.xDimension / 2, y + def.dimensions.yDimension + 15);
        }

        // Highlight active labware
        const activeInfo = getLabwareAndWellInfo(command.payload.text || '');
        if (activeInfo) {
            const activeId = `${activeInfo.labware}_${activeInfo.slot}`;
            const activeLoc = labwareLocations[activeId];
            const activeDef = labwareDefinitions[activeLoc.loadName];
            if (activeLoc && activeDef) {
                 const [x, y] = slotPositions[activeLoc.slot];
                 ctx.strokeStyle = 'red';
                 ctx.lineWidth = 2;
                 ctx.strokeRect(x, y, activeDef.dimensions.xDimension, activeDef.dimensions.yDimension);
            }
        }
    }

    function togglePlayPause() {
        if (animationTimer) {
            clearInterval(animationTimer);
            animationTimer = null;
            playPauseBtn.textContent = 'Play';
        } else {
            playPauseBtn.textContent = 'Pause';
            animationTimer = setInterval(() => {
                let nextFrame = currentFrame + 1;
                if (nextFrame >= runlog.length) {
                    nextFrame = 0; // Loop
                }
                drawFrame(nextFrame);
            }, 800);
        }
    }

    // --- Helpers ---
    function getLabwareAndWellInfo(text) {
        const match = text.match(/(from|into|in) (.+?) of (.+?) on slot (\d+)/);
        if (match) {
            const [_p, well, labware, slot] = match;
            return { well, labware, slot };
        }
        return null;
    }

    function guessLoadName(labwareName) {
        // This is a fragile hack. A better solution would involve parsing `loadLabware` commands.
        let guess = labwareName.replace(/Opentrons OT-2 /g, '').replace(/ /g, '_').toLowerCase();
        if (guess.includes('tip_rack')) {
            return 'opentrons_96_tiprack_300ul';
        }
        if (guess.includes('fixed_trash')) {
            return 'opentrons_1_trash_1100ml_fixed';
        }
        if (guess.includes('corning_96_wellplate_360_μl_flat')) {
             return 'corning_96_wellplate_360ul_flat';
        }
        return guess;
    }

    async function fetchLabwareDefinition(loadName) {
        if (labwareDefinitions[loadName]) {
            return labwareDefinitions[loadName];
        }
        try {
            const response = await fetch(`/labware/${loadName}`);
            if (!response.ok) throw new Error(`Labware '${loadName}' not found`);
            const definition = await response.json();
            labwareDefinitions[loadName] = definition;
            return definition;
        } catch (error) {
            console.error(error);
            return null;
        }
    }
});
