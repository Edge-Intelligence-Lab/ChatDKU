# How to develop the frontend

## Install dependencies

Make sure you have Node JS installed.

## Set up the development environment

Inside the `frontend/` folder, use `npm ci` to clean-install all the dependencies.

Run `npm run dev` to load a hot-reloading development build on your local machine. This allows you to quickly see changes you make to the website.

Please note that API calls may not work in a dev instance due to SSL requirements.

## Updating deployment

1. Before changing anything in the deployment, locally test `npm run build`.It should successfully build a static export in the `frontend/out/` directory.

2. Push your changes to the repo

3. Pull the repo on GPU3 (or use `sftp` to copy the `frontend/` folder into a directory on GPU3, which can be faster than trying to use `git pull`).

4. Inside your `frontend/` folder on GPU3, run `npm ci` and then `npm run build`. If this succeeds, you should see a `out/` folder inside the `frontend/` directory.

5. Sync the build:

    ```bash
    sudo rsync -av --delete out/ /var/www/chatdku/
    ```

6. Reload Apache:

    ```bash
    sudo apachectl configtest && sudo systemctl reload apache2
    ```

7. Test it by going to <https://chatdku.dukekunshan.edu.cn/> on incognito mode in any browser.
