YOUR OWN MODEL PHOTOS
=====================

Want to be the models for the store? Put your photos here, then run:

    flask --app wsgi load-model-photos

(With the virtual environment active. On Windows, run it in the same Command Prompt where you ran scripts\setup.bat.)

1) Big site photos: name the file after the spot it fills (jpg, png or webp):

    hero.jpg       the large photo at the top of the homepage
    lookbook.jpg   the "Meet our models" tile
    promo.jpg      the sale banner
    login.jpg      the sign-in page
    register.jpg   the create-account page

2) Product photos: make a folder named after the product's web address (its "slug"),
   e.g. for  /shop/p/linen-wrap-midi-dress  use:

    products/linen-wrap-midi-dress/01.jpg
    products/linen-wrap-midi-dress/02.jpg

   Your first photo becomes the product's cover image; any extra photos join its gallery.

Tips: portrait photos (taller than wide), at least 1200 px tall, plain or tidy background.
Photos are checked, resized and re-saved safely when they're loaded.
You can also upload one at a time in Seller studio > Model photos, or on any product's edit page.

Product slugs in the demo data:
  Clothing (women): linen-wrap-midi-dress, red-silk-slip-dress, cropped-leather-biker-jacket,
                    relaxed-straight-jeans, structured-leather-tote
  Clothing (men):   tailored-wool-suit, heavyweight-white-tee, utility-field-jacket,
                    red-runner-sneakers, tortoiseshell-sunglasses
  Watches:          minimalist-leather-strap-watch, chronograph-steel-watch,
                    classic-gold-tone-dress-watch, diver-automatic-200m, smart-fitness-watch
  Jewelry:          18k-gold-stacking-rings-set-of-3, freshwater-pearl-drop-earrings,
                    diamond-solitaire-pendant, sterling-silver-chain-bracelet, signature-jewelry-gift-set
  Cars:             classic-red-sports-coupe-pre-owned, silver-luxury-sports-car-pre-owned,
                    midnight-muscle-coupe-pre-owned, electric-crossover-suv
  Gifts:            luxury-gift-box, 72-dark-chocolate-bar, single-origin-coffee-beans, scented-soy-candle
