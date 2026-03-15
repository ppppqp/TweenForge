/**
 * TweenForge — Clip Studio Paint Host Adapter
 *
 * This script implements the HostBridge interface that panel.html expects.
 * It handles CSP-specific frame export/import and launches the HTML panel.
 *
 * Installation:
 *   1. Start the TweenForge server:  tweenforge serve
 *   2. In CSP: Window > Plugin Panel > Load Plugin... > select this folder
 *      Or: File > Script > Run Script... > select this file
 *
 * CSP v2.x+ supports HTML panels via the Palette API. This script registers
 * the panel and injects the HostBridge before the panel HTML loads.
 */

(function () {
    "use strict";

    // -----------------------------------------------------------------------
    // Configuration
    // -----------------------------------------------------------------------

    var CONFIG_PATH = null;
    var SERVER_URL = "http://127.0.0.1:9817";
    var TEMP_DIR = "";

    function initConfig() {
        // Try to read config from ~/.tweenforge/csp_config.json
        try {
            var home = csp.getenv ? csp.getenv("HOME") : "~";
            var configFile = home + "/.tweenforge/csp_config.json";
            var content = csp.fs.readFileSync(configFile, "utf8");
            var cfg = JSON.parse(content);
            SERVER_URL = cfg.server_url || SERVER_URL;
            TEMP_DIR = cfg.temp_dir || "";
        } catch (e) {
            // Config not found — use defaults
        }
        if (!TEMP_DIR) {
            TEMP_DIR = csp.app.tempPath + "/tweenforge";
        }
    }

    // -----------------------------------------------------------------------
    // CSP Frame Export / Import
    // -----------------------------------------------------------------------

    function ensureDir(path) {
        try {
            csp.fs.mkdirSync(path, { recursive: true });
        } catch (e) {
            // May already exist
        }
    }

    /**
     * Export a single animation cel as PNG.
     *
     * CSP v2.x approach: navigate to the frame, flatten visible layers,
     * and save using the document export API.
     */
    function exportFrame(frameNumber, outputPath) {
        return new Promise(function (resolve, reject) {
            try {
                var doc = csp.app.activeDocument;
                if (!doc) {
                    reject(new Error("No active document"));
                    return;
                }

                // Navigate to the target frame
                doc.timeline.currentFrame = frameNumber;

                // Ensure output directory exists
                var dir = outputPath.substring(0, outputPath.lastIndexOf("/"));
                ensureDir(dir);

                // Export the current frame as PNG
                // CSP v2.x provides doc.exportImage() for programmatic export
                var exportOpts = {
                    format: "png",
                    path: outputPath,
                    flattenLayers: true,
                };

                // Try the programmatic export API first
                if (doc.exportImage) {
                    doc.exportImage(exportOpts);
                    resolve(outputPath);
                } else {
                    // Fallback: use rasterized layer data
                    // Save active layer as PNG via canvas rasterization
                    var layer = doc.activeLayer;
                    if (layer && layer.exportTo) {
                        layer.exportTo(outputPath, "png");
                        resolve(outputPath);
                    } else {
                        reject(new Error(
                            "CSP version does not support programmatic export. " +
                            "Please export frames manually and use the CLI."
                        ));
                    }
                }
            } catch (e) {
                reject(e);
            }
        });
    }

    /**
     * Import a PNG as a new animation cel at the target frame.
     */
    function importFrame(imagePath, frameNumber) {
        return new Promise(function (resolve, reject) {
            try {
                var doc = csp.app.activeDocument;
                if (!doc) {
                    reject(new Error("No active document"));
                    return;
                }

                // Navigate to target frame
                doc.timeline.currentFrame = frameNumber;

                // Import the image as a new layer
                if (doc.importImage) {
                    doc.importImage({
                        path: imagePath,
                        asNewLayer: true,
                    });
                    resolve();
                } else if (csp.app.executeMenuCommand) {
                    // Fallback: use menu command (may show dialog)
                    csp.app.executeMenuCommand("file_import");
                    resolve();
                } else {
                    reject(new Error(
                        "CSP version does not support programmatic import. " +
                        "Please import frames manually from: " + imagePath
                    ));
                }
            } catch (e) {
                reject(e);
            }
        });
    }

    // -----------------------------------------------------------------------
    // HostBridge — the interface that panel.html expects
    // -----------------------------------------------------------------------

    var HostBridge = {
        getServerUrl: function () {
            return SERVER_URL;
        },

        getTempDir: function () {
            return TEMP_DIR;
        },

        exportFrame: exportFrame,
        importFrame: importFrame,

        onReady: function () {
            // Panel has loaded and initialized
            csp.log("[TweenForge] Panel ready, server=" + SERVER_URL);
        },
    };

    // -----------------------------------------------------------------------
    // Panel registration
    // -----------------------------------------------------------------------

    function launchPanel() {
        initConfig();

        // CSP v2.x HTML panel registration
        if (csp.app.registerHTMLPanel) {
            csp.app.registerHTMLPanel({
                id: "tweenforge",
                title: "TweenForge",
                htmlFile: __dirname + "/panel.html",
                width: 280,
                height: 500,
                bridge: HostBridge,
            });
        } else {
            // Older CSP: fall back to opening panel.html in a dialog
            // or prompt the user to use the CLI
            csp.alert(
                "TweenForge requires CSP v2.x+ for HTML panel support.\n\n" +
                "You can still use the CLI:\n" +
                "  tweenforge generate frameA.png frameB.png -n 3\n\n" +
                "Or upgrade CSP to use the panel UI."
            );
        }
    }

    // Auto-launch on script load
    launchPanel();

})();
