# License activation server (Render)

Deploy only this folder to a **separate** Git repo so your main project stays private.

## Expiry and renewal

- **After the licence expiry date**, the app will not allow login (server returns "License expired").
- **Renewal options:**
  1. **New key:** Generate a new key with extended expiry (e.g. `python license_keygen.py MGMINN 20271231`) and give it to the customer. They use **Activate License** and enter the new key; the app gets a new token and works until the new expiry.
  2. **Extend on server (no new key):** After the customer pays, you extend their current activation. Set `ADMIN_SECRET` in Render (Environment). Then run:  
     `LICENSE_SERVER_URL=https://your-app.onrender.com ADMIN_SECRET=yoursecret python extend_license.py LICENSE_KEY CLIENT_ID 2027-12-31`  
     Use the same `LICENSE_KEY` you issued and the customer’s machine name as `CLIENT_ID`. The customer does nothing; on next app launch the server returns the new expiry.

## 1. Use this as your only Git repo for Render

```bash
cd license-server-render
git init
git add .
git commit -m "License server for Render"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_LICENSE_SERVER_REPO.git
git push -u origin main
```

Your repo will contain:

- `license_server.py`, `license_utils.py`
- `requirements.txt`, `render.yaml`, `README.md`
- `extend_license.py` (renew expiry from your PC), `list_activations.py` (view stored activations)

## 2. Deploy on Render

1. Go to [dashboard.render.com](https://dashboard.render.com) → **New** → **Blueprint**.
2. Connect the **license-server-render** repo (the one that has only these files).
3. Add **Environment** variables (Render Dashboard → your service → **Environment** → Add):
   - **LICENSE_SECRET** (Secret) = same value as in your `license_keygen.py`.
   - **ADMIN_SECRET** (Secret) = a strong password only you know; used to list activations and extend expiry.
   - **APP_LATEST_VERSION** (optional) = current app version for update check (e.g. `1.0.0`). Customers see “New update available” when this is newer than their app.
   - **APP_DOWNLOAD_URL** (optional) = URL to download the new installer/exe (e.g. your website or file host). Used when the customer clicks “Download update”.
4. Deploy. Your URL will be like `https://resortmanager-license-server.onrender.com`.

### Where to store ADMIN_SECRET

- **On the server (Render):** In the **Environment** tab of your Web Service. Add variable `ADMIN_SECRET`, paste your secret, and mark it as **Secret** so it’s hidden. Never commit this value in code or Git.
- **On your PC (for scripts):** When you run `list_activations.py` or `extend_license.py`, set it as an environment variable for that run, e.g.  
  `set ADMIN_SECRET=your_secret` (Windows) or `export ADMIN_SECRET=your_secret` (Mac/Linux). Optionally use a `.env` file in the same folder (e.g. `ADMIN_SECRET=...`) and load it in the script; keep `.env` out of Git (add to `.gitignore`).

## 3. View stored activations (vendor records)

From your PC, with the same repo (or the `license-server-render` folder):

```bash
set LICENSE_SERVER_URL=https://your-app.onrender.com
set ADMIN_SECRET=your_admin_secret
python list_activations.py
```

This calls the server’s **GET /api/admin/activations** and prints a table: license key, client ID (machine name), expiry, activated at, and a partial token. You can also open in a browser (use the secret only on your machine, not in shared links):

`https://your-app.onrender.com/api/admin/activations?admin_secret=YOUR_SECRET`

The response is JSON. Use `list_activations.py` for a readable table.

## 4. In your desktop app

Configuration → **License server URL** = `https://your-service-name.onrender.com` (no trailing slash).
