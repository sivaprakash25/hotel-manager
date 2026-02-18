# License activation server (Render)

Deploy only this folder to a **separate** Git repo so your main project stays private.

## 1. Use this as your only Git repo for Render

```bash
cd license-server-render
git init
git add .
git commit -m "License server for Render"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_LICENSE_SERVER_REPO.git
git push -u origin main
```

Your repo will contain only:

- `license_server.py`
- `license_utils.py`
- `requirements.txt`
- `render.yaml`
- `README.md`

## 2. Deploy on Render

1. Go to [dashboard.render.com](https://dashboard.render.com) → **New** → **Blueprint**.
2. Connect the **license-server-render** repo (the one that has only these files).
3. Add **Environment** variable: **LICENSE_SECRET** (Secret) = same value as in your `license_keygen.py`.
4. Deploy. Your URL will be like `https://resortmanager-license-server.onrender.com`.

## 3. In your desktop app

Configuration → **License server URL** = `https://your-service-name.onrender.com` (no trailing slash).
