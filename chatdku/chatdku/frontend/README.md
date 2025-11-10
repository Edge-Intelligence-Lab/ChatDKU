# ChatDKU Website Developer Documentation

Last updated by Anar Nyambayar, October 2025

## Our Stack:

We're using the Next.js framework for its quick development opportunities and rich open-source community. Since our backend is handled by Django, we are serving the website as a static site using `next build`.

We're using the [shadcn/ui](https://ui.shadcn.com/) open-source UI library. This is a widely used, simple, and customizable UI library that uses Tailwind CSS for globally consistent styling.

Try to stick to these shadcn/ui components as much as possible, and only create custom components when necessary. This is to keep accessibility standards and consistency.

## Development Guide:

### Dependencies:

- The latest Node.js LTS runtime must be installed on the machine you're using to develop.

### Development flow:

1. Run `npm install` in the frontend directory to install Node dependencies.
2. Run `npm run dev` to spin up a localhost server and navigate to http://localhost:3000/ to see the homepage. The dev server will hot-reload whenever you save.
3. Make necessary edits, and review changes on both a desktop screen and a mobile screen. Test with many aspect ratios to make sure nothing clips or looks broken. You can also enter "test" in the chat box to test proper markdown rendering (this is important as users must be able to read ChatDKU's responses easily).
4. Check that `npm run build` succeeds before pushing to the main branch.

### Deploying to production:

1. Run `npm run build`. If successful, a folder called `out/` will have been compiled.
2. Run the command `sudo rsync -av --delete out/ /var/www/chatdku/` on the server to update the frontend files on deployment.
3. Visit [ChatDKU](chatdku.dukekunshan.edu.cn) in incognito mode. Make sure the chat responses are clear and legible.
