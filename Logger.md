# Logger.md

A running log of questions raised and resolutions made in this repository.

---

## 2026-03-23

### Issue 1 — npm install shows deprecated warnings and vulnerabilities
**Query:** Running `npm install` produced multiple deprecation warnings (rimraf, glob, puppeteer, etc.) and 8 vulnerabilities. Why does this happen and how to prevent it for future users?

**Resolution:** The deprecations come from `whatsapp-web.js`'s own transitive dependencies using older packages — not directly from this project's code. These cannot be eliminated without `whatsapp-web.js` updating its own deps. The vulnerabilities were resolved by running `npm audit fix`. To prevent future users needing to repeat this step, `package-lock.json` should be committed to the repo — it locks all resolved and audited package versions so `npm install` reproduces the exact same tree without re-resolving or re-auditing.

---

### Issue 2 — Best practice for installing Python dependencies
**Query:** Used `venv` to install Python packages after being blocked by the system-managed environment error. Is there a better or more efficient way?

**Resolution:** Using `venv` is the correct approach on modern Debian/Ubuntu systems. The improvement made was adding a `requirements.txt` file listing `firebase-admin` and `requests`. Future users now only need to run:
```bash
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
```
instead of manually knowing which packages to install.

---

### Issue 3 — UserWarning: Detected filter using positional arguments (Firestore)
**Query:** Running the bot printed `UserWarning: Detected filter using positional arguments. Prefer using the 'filter' keyword argument instead.` for `.where()` calls in `wordle_firebase.py`.

**Resolution:** The `firebase-admin` SDK deprecated positional arguments in `.where()` calls. All three call sites in `wordle_firebase.py` were updated to use the `FieldFilter` class from `google.cloud.firestore_v1.base_query`:
```python
# Before
results_ref.where("puzzle", "==", puzzle)

# After
results_ref.where(filter=FieldFilter("puzzle", "==", puzzle))
```
The import `from google.cloud.firestore_v1.base_query import FieldFilter` was also added. The unused `import sqlite3` was removed at the same time.

---

### Issue 4 — QR code image not deleted after authentication
**Query:** After the WhatsApp QR code is scanned and the bot connects, the `whatsapp-qr.png` file remains on disk. It should be cleaned up automatically.

**Resolution:** The QR file is only needed until the user scans it to authenticate. Once scanned, WhatsApp fires the `ready` event in `bot.js`, signalling a successful connection. The deletion is placed there rather than in the `qr` event (where the file is created) because the `qr` event has no way of knowing if the scan was successful — only `ready` confirms that. `fs.unlink` is used with an `ENOENT` guard so it silently skips deletion on subsequent runs where no QR was generated (session already cached in `.wwebjs_auth/`).
```js
const fs = require('fs');

client.on('ready', () => {
    console.log('WhatsApp Bot Ready!');
    fs.unlink('whatsapp-qr.png', err => {
        if (err && err.code !== 'ENOENT') console.error('Failed to delete QR code:', err);
    });
});
```

---
