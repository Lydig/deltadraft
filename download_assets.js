// download_assets.js
const fs = require('fs');
const path = require('path');
const https = require('https');

const DDRAGON_VERSION = "14.13.1";
const DDRAGON_BASE = `https://ddragon.leagueoflegends.com/cdn/${DDRAGON_VERSION}`;
const CHAMPION_IMG_DIR = path.join(__dirname, 'desktop-app', 'assets', 'champions');

async function downloadFile(url, dest) {
    return new Promise((resolve, reject) => {
        const file = fs.createWriteStream(dest);
        https.get(url, response => {
            response.pipe(file);
            file.on('finish', () => {
                file.close(resolve);
            });
        }).on('error', err => {
            fs.unlink(dest);
            reject(err.message);
        });
    });
}

async function downloadChampionImages() {
    console.log("Fetching champion list...");
    if (!fs.existsSync(CHAMPION_IMG_DIR)) {
        fs.mkdirSync(CHAMPION_IMG_DIR, { recursive: true });
    }

    const response = await fetch(`${DDRAGON_BASE}/data/en_US/champion.json`);
    const champData = await response.json();
    const champions = Object.values(champData.data);

    console.log(`Found ${champions.length} champions. Starting download...`);

    for (const champ of champions) {
        const imageUrl = `${DDRAGON_BASE}/img/champion/${champ.image.full}`;
        const destPath = path.join(CHAMPION_IMG_DIR, champ.image.full);
        if (!fs.existsSync(destPath)) {
            try {
                await downloadFile(imageUrl, destPath);
                console.log(`Downloaded ${champ.name}`);
            } catch (error) {
                console.error(`Failed to download ${champ.name}: ${error}`);
            }
        }
    }
    console.log("Champion image download complete.");
}

downloadChampionImages();