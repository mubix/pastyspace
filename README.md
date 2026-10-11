# PastySpace website

The `gh-pages` branch contains only the product website and its screenshot maintenance tool. The application source lives on [`main`](https://github.com/mubix/pastyspace/tree/main).

The website is plain HTML, CSS, JavaScript, and local assets at the branch root, with no build step. The introduction, features, and deployment guide are `index.html`, `features.html`, and `deploy.html`.

## Preview locally

From the repository root:

```sh
python3 -m http.server 8080 --bind 127.0.0.1
```

Open <http://localhost:8080/>. Check all three pages at desktop and mobile widths, including the navigation, screenshots, and copy buttons.

## Publish when ready

1. Review the files, commit the intended changes on `gh-pages`, then push that branch to GitHub.
2. In the repository, open **Settings → Pages**.
3. Under **Build and deployment**, choose **Deploy from a branch**.
4. Choose branch **gh-pages** and folder **/ (root)**, then click **Save**.
5. Check the Pages deployment in the repository's Actions tab. The expected address is <https://mubix.github.io/pastyspace/>.

Keep `.nojekyll` at the branch root so these static files are served without a Jekyll build. Keep links relative, such as `assets/logo.svg` and `deploy.html`, so the site works at the repository URL. GitHub documents the branch and folder options in [Configuring a publishing source](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).

GitHub Free supports Pages for public repositories; private repository support depends on the plan. Enable publishing when the repository and website are ready for public access. See [Creating a GitHub Pages site](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site).

## Website and application hosting

GitHub Pages serves this static website. It cannot run the Flask application or store pastes in SQLite. Run the application separately using the instructions on `deploy.html`, which clone the `main` branch with its Docker Compose configuration. See [What is GitHub Pages?](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages) and [Docker Compose up](https://docs.docker.com/reference/cli/docker/compose/up/).

## Maintain the site

- Edit page content directly in the HTML files; shared styles and behavior live under `assets/`. Keep navigation and footer changes consistent across the pages.
- `assets/logo.svg` and `assets/pasty.svg` contain the website's custom artwork.
- Product screenshots live under `assets/screenshots/`. The repeatable `tools/capture_screenshots.py` script accepts a separate app checkout with `--app-dir`, creates demonstration pastes, captures the real app, and removes its temporary database. Its docstring lists the optional capture dependencies; they are not needed to serve this website. Update image dimensions and alt text when replacing an image.
- Bricolage Grotesque and DM Sans are served locally from `assets/fonts/`. Keep their accompanying Open Font License files with the fonts.
- Preview after editing. Keep links and image paths relative so they also work under the published `/pastyspace/` URL prefix. Inspect narrow screens and use the keyboard to test interactive controls. There is no package installation or compilation step.

Changes become public after you commit and push them to the configured publishing branch.
