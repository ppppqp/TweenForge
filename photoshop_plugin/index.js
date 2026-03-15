/**
 * TweenForge — Photoshop UXP Host Adapter
 *
 * Implements the same HostBridge interface as the CSP adapter, so the shared
 * panel.html UI works identically in both applications.
 *
 * Photoshop UXP API docs: https://developer.adobe.com/photoshop/uxp/2022/
 *
 * Installation:
 *   1. Start TweenForge server:  tweenforge serve
 *   2. In Photoshop: Plugins > Development > Load Plugin... > select this folder
 *   3. The TweenForge panel appears under Plugins menu
 */

const { app, core, action } = require("photoshop");
const { localFileSystem: fs } = require("uxp").storage;

// -----------------------------------------------------------------------
// Configuration
// -----------------------------------------------------------------------

const SERVER_URL = "http://127.0.0.1:9817";

function getTempDir() {
    return require("os").tmpdir() + "/tweenforge";
}

// -----------------------------------------------------------------------
// Photoshop Frame Export / Import
//
// In Photoshop, "frames" are typically layers in a video timeline
// or individual layers in a layer group. We treat each layer as a frame.
// -----------------------------------------------------------------------

/**
 * Export a frame (layer) as PNG.
 *
 * For video timeline workflows, frameNumber corresponds to the timeline
 * frame. For layer-based workflows, it's the layer index.
 */
async function exportFrame(frameNumber, outputPath) {
    return await core.executeAsModal(async () => {
        const doc = app.activeDocument;
        if (!doc) throw new Error("No active document");

        // Navigate to the timeline frame
        if (doc.timeline) {
            await action.batchPlay([{
                _obj: "set",
                _target: [{ _ref: "timeline" }],
                currentFrame: frameNumber,
            }], {});
        }

        // Export as PNG using batchPlay
        const folder = await fs.getFolder();
        await doc.saveAs.png(outputPath, {
            compression: 6,
            interlaced: false,
        });

        return outputPath;
    }, { commandName: "TweenForge: Export Frame" });
}

/**
 * Import a PNG as a new layer at the target frame position.
 */
async function importFrame(imagePath, frameNumber) {
    return await core.executeAsModal(async () => {
        const doc = app.activeDocument;
        if (!doc) throw new Error("No active document");

        // Place the image as a new layer
        await action.batchPlay([{
            _obj: "placeEvent",
            null: { _path: imagePath, _kind: "local" },
            freeTransformCenterState: { _enum: "quadCenterState", _value: "QCSAverage" },
        }], {});

        // If timeline exists, move the layer to the target frame
        if (doc.timeline) {
            await action.batchPlay([{
                _obj: "set",
                _target: [{ _ref: "timeline" }],
                currentFrame: frameNumber,
            }], {});
        }
    }, { commandName: "TweenForge: Import Frame" });
}

// -----------------------------------------------------------------------
// HostBridge — same interface as the CSP adapter
// -----------------------------------------------------------------------

const HostBridge = {
    getServerUrl: () => SERVER_URL,
    getTempDir: getTempDir,
    exportFrame: exportFrame,
    importFrame: importFrame,
    onReady: () => console.log("[TweenForge] Photoshop panel ready"),
};

// -----------------------------------------------------------------------
// Panel setup — load the shared panel.html
// -----------------------------------------------------------------------

const { entrypoints } = require("uxp");

entrypoints.setup({
    panels: {
        tweenforgePanel: {
            show(event) {
                // Inject HostBridge into the panel's webview context
                const panelEl = document.getElementById("tweenforge-root");
                if (!panelEl) return;

                // The panel HTML is loaded as the entrypoint's content
                // HostBridge is available globally from this module scope
                window.HostBridge = HostBridge;
            },
            hide(event) {},
        },
    },
});
