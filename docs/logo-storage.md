# Logo Storage

Use this folder for client logos:

- `assets/logos/client-name.png`
- `assets/logos/client-name.webp`
- `assets/logos/client-name.svg`

Recommended format:

- `PNG` with transparent background
- square image
- `512x512` or larger

Example GitHub Pages URL:

```text
https://granlol.github.io/manicure-webapp/assets/logos/client-name.png
```

Example config:

```js
salonLogoUrl: "https://granlol.github.io/manicure-webapp/assets/logos/client-name.png",
salonLogoText: "",
salonTagline: "online booking",
```

If there is no real logo:

```js
salonLogoUrl: "",
salonLogoText: "NS",
salonTagline: "online booking",
```

Text-only mode:

```js
salonLogoUrl: "",
salonLogoText: "",
salonTagline: "online booking",
```
