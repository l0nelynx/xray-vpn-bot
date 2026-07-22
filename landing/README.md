# Project landing page

Static shadcn-style homepage for GitHub Pages (`/`). MkDocs is published at `/docs/`.

## Local preview

```bash
mkdir -p site/assets/screenshots
cp landing/index.html landing/styles.css landing/carousel.js landing/stats.js site/
cp docs/screenshots/*.png site/assets/screenshots/
python -m http.server -d site 8080
```

Full assemble (with MkDocs) is documented in `docs/README.md` and `.github/workflows/docs.yml`.
