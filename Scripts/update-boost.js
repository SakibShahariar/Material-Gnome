#!/usr/bin/env node

const fs = require('fs');

// --- ABSOLUTE PATHS ---
const CSS_FILE = '/home/sakib/.zen/oup922t1.Default (release)/chrome/colors.css';
const JSON_FILE = '/home/sakib/.config/zen-boosts/Matugen.json';

// Helper: Convert HEX to HSL
function hexToHsl(hex) {
    hex = hex.replace('#', '');
    let r = parseInt(hex.substring(0, 2), 16) / 255;
    let g = parseInt(hex.substring(2, 4), 16) / 255;
    let b = parseInt(hex.substring(4, 6), 16) / 255;

    let max = Math.max(r, g, b), min = Math.min(r, g, b);
    let h, s, l = (max + min) / 2;

    if (max === min) {
        h = s = 0;
    } else {
        let d = max - min;
        s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
        switch (max) {
            case r: h = (g - b) / d + (g < b ? 6 : 0); break;
            case g: h = (b - r) / d + 2; break;
            case b: h = (r - g) / d + 4; break;
        }
        h /= 6;
    }

    return {
        hue: Math.round(h * 360),
        saturation: parseFloat(s.toFixed(4)),
        brightness: parseFloat(l.toFixed(4))
    };
}

try {
    if (!fs.existsSync(CSS_FILE)) {
        console.error(`Error: Cannot find CSS file at: ${CSS_FILE}`);
        process.exit(1);
    }
    const cssContent = fs.readFileSync(CSS_FILE, 'utf8');

    const primaryMatch = cssContent.match(/--primary:\s*(#[a-fA-F0-9]{6})/);
    const bgMatch = cssContent.match(/--background:\s*(#[a-fA-F0-9]{6})/);

    if (!primaryMatch || !bgMatch) {
        console.error("Could not extract both '--primary' and '--background' from colors.css.");
        process.exit(1);
    }

    const primaryHsl = hexToHsl(primaryMatch[1]);
    const bgHsl = hexToHsl(bgMatch[1]);

    if (!fs.existsSync(JSON_FILE)) {
        console.error(`Error: Cannot find Boost JSON file at: ${JSON_FILE}`);
        process.exit(1);
    }
    const boostData = JSON.parse(fs.readFileSync(JSON_FILE, 'utf8'));

    // 1. BASE HUE ANCHORED TO PRIMARY ACCENT
    boostData.dotAngleDeg = primaryHsl.hue;

    // LOCKED AT YOUR SWEET SPOT (75% Saturation)
    boostData.saturation = 0.75;

    // 2. BACKDROP LIGHTING LOCKED TO THEME SPECIFICATION
    boostData.brightness = bgHsl.brightness;

    // LOCKED AT YOUR SWEET SPOT (50% Contrast)
    boostData.contrast = 0.50;

    // 3. COMPUTE THE DISPLACEMENT DELTA RADIANS TOWARD THE BACKGROUND HUE
    let delta = bgHsl.hue - primaryHsl.hue;
    if (delta > 180) delta -= 360;
    if (delta < -180) delta += 360;

    boostData.secondaryDotAngleDegDelta = parseFloat(delta.toFixed(4));

    // 4. RESTORE ARC'S OPTIMAL LAYOUT CONFIGURATION COORDINATES
    boostData.dotPos = {
        x: 0.5047,
        y: 0.1645
    };
    boostData.secondaryDotPos = {
        x: 0.7683,
        y: 0.2986
    };

    boostData.changeWasMade = true;

    fs.writeFileSync(JSON_FILE, JSON.stringify(boostData, null, 2), 'utf8');

} catch (error) {
    console.error("Pipeline error:", error.message);
}
