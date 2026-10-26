"""Fictional demonstration content. None of these houses or perfumes exist."""

SELLERS = [
    {
        "id": "ombre-atlas",
        "name": "Ombre Atlas",
        "tagline": "Resins, smoke and the long shadow of the desert.",
        "description": "A fictional house working in amber, oud and incense. Ombre Atlas blends slowly, ages its "
        "tinctures for months and bottles them in heavy smoked glass meant to sit on a dresser for years.",
        "origin": "Marrakech",
        "founded": 2011,
        "accent": "#8a5a2b",
        "bottle": "block",
    },
    {
        "id": "casa-ylang",
        "name": "Casa Ylang",
        "tagline": "Philippine botanicals, distilled close to the source.",
        "description": "A fictional Manila atelier built around island flora: ylang-ylang from Anao, sampaguita, "
        "calamansi and dama de noche. Bright, humid and unapologetically floral.",
        "origin": "Manila",
        "founded": 2017,
        "accent": "#b08a3e",
        "bottle": "dome",
    },
    {
        "id": "nordlys",
        "name": "Nordlys Parfum",
        "tagline": "Cold air, pale wood, the sea at six in the morning.",
        "description": "A fictional Scandinavian house of quiet, transparent scents. Nordlys works with very few "
        "materials per formula, so every note can be heard.",
        "origin": "Bergen",
        "founded": 2014,
        "accent": "#6f7f86",
        "bottle": "column",
    },
    {
        "id": "velours-noir",
        "name": "Velours Noir",
        "tagline": "Parisian excess, worn after dark.",
        "description": "A fictional Paris house that never learned restraint. Velours Noir makes gourmands and "
        "chypres with velvet texture, cut in faceted crystal-style flacons.",
        "origin": "Paris",
        "founded": 2008,
        "accent": "#5b2333",
        "bottle": "facet",
    },
]


def p(id, seller_id, name, price_php, family, conc, size, stock, hue, top, heart, base, desc, best=False):
    return {
        "id": id, "seller_id": seller_id, "name": name, "price_centavos": price_php * 100,
        "family": family, "concentration": conc, "size_ml": size, "stock": stock, "hue": hue,
        "top_notes": top, "heart_notes": heart, "base_notes": base, "description": desc, "bestseller": best,
    }


PRODUCTS = [
    # Ombre Atlas
    p("atlas-oud-nocturne", "ombre-atlas", "Oud Nocturne", 14800, "Amber", "Parfum", 50, 8, "#4a2a14",
      ["Saffron", "Black pepper"], ["Agarwood", "Damask rose"], ["Labdanum", "Leather", "Smoked birch"],
      "A slow-burning oud lit with saffron and pepper, softened by a single rose petal and left to smoulder "
      "on leather and birch tar. Built for evenings that end late.", True),
    p("atlas-sable-dore", "ombre-atlas", "Sable Doré", 9600, "Amber", "EDP", 100, 14, "#a8702c",
      ["Bergamot", "Cardamom"], ["Benzoin", "Orris"], ["Tonka bean", "Vanilla absolute", "Musk"],
      "Warm sand at the hour the light turns gold. Cardamom and bergamot open onto a resinous benzoin heart "
      "that dries down to a skin-close tonka glow."),
    p("atlas-fumee-sacree", "ombre-atlas", "Fumée Sacrée", 11200, "Woody", "EDP", 75, 6, "#5d4a3a",
      ["Elemi", "Pink pepper"], ["Frankincense", "Myrrh"], ["Cedar", "Guaiac wood", "Ambergris accord"],
      "Incense drifting through a cedar-lined room. Dry, mineral and contemplative, with a pink pepper spark "
      "that keeps it from feeling solemn."),
    p("atlas-medina-rose", "ombre-atlas", "Medina Rose", 8900, "Floral", "EDP", 50, 0, "#9b3d3d",
      ["Pomegranate", "Clove"], ["Taif rose", "Geranium"], ["Patchouli", "Amber"],
      "A spiced market rose: pomegranate juice, a crushed clove and dense Taif petals over a patchouli and "
      "amber base. Currently sold out to show the out-of-stock state."),
    p("atlas-cuir-de-nuit", "ombre-atlas", "Cuir de Nuit", 12500, "Woody", "Parfum", 50, 4, "#2f2119",
      ["Juniper", "Saffron"], ["Suede", "Violet leaf"], ["Vetiver", "Castoreum accord", "Oakmoss"],
      "The inside of a vintage leather jacket. Suede and violet leaf over smoky vetiver, polished and quietly "
      "animalic."),
    # Casa Ylang
    p("ylang-anao", "casa-ylang", "Anao", 6800, "Floral", "EDP", 50, 18, "#e2c169",
      ["Calamansi", "Green mango"], ["Ylang-ylang", "Tuberose"], ["Coconut husk", "Sandalwood"],
      "Named for the fictional groves that supply our ylang-ylang. A sunlit floral that starts sour-green with "
      "calamansi and blooms into creamy, golden ylang.", True),
    p("ylang-sampaguita-hour", "casa-ylang", "Sampaguita Hour", 5900, "Floral", "EDT", 100, 22, "#f1e6c8",
      ["Neroli", "Pear"], ["Sampaguita", "Orange blossom"], ["White musk", "Ambrette"],
      "Jasmine garlands sold at a church gate. Airy, white and tender, an everyday floral that sits close to the "
      "skin."),
    p("ylang-dama-de-noche", "casa-ylang", "Dama de Noche", 7400, "Floral", "Parfum", 30, 9, "#cfa94a",
      ["Lime leaf", "Nutmeg"], ["Night-blooming jasmine", "Gardenia"], ["Benzoin", "Vanilla", "Cashmeran"],
      "The flower that only opens after dark. Narcotic gardenia and night jasmine over a soft vanilla "
      "benzoin: humid, heady, magnetic."),
    p("ylang-calamansi-salt", "casa-ylang", "Calamansi & Salt", 4800, "Fresh", "EDT", 100, 30, "#d7dd8c",
      ["Calamansi", "Sea salt", "Ginger"], ["Pandan leaf", "Basil"], ["Driftwood", "Vetiver"],
      "A tart, salty citrus for heat and humidity. Calamansi and ginger fizz over pandan and sun-bleached "
      "driftwood.", True),
    p("ylang-tsokolate", "casa-ylang", "Tsokolate", 6200, "Gourmand", "EDP", 50, 12, "#6b3e26",
      ["Cacao nib", "Orange zest"], ["Muscovado", "Tablea chocolate"], ["Toasted rice", "Tonka", "Vanilla"],
      "Thick tablea hot chocolate on a rainy morning. Bitter cacao and muscovado on a toasted rice and tonka "
      "base: comforting, never sugary."),
    # Nordlys
    p("nordlys-fjord", "nordlys", "Fjord", 7900, "Fresh", "EDT", 100, 20, "#bcd3d6",
      ["Sea spray", "Juniper berry"], ["Seaweed absolute", "Clary sage"], ["Grey ambergris accord", "Musk"],
      "Cold seawater against granite. A clean, mineral aquatic with juniper and sage, nothing sweet "
      "about it.", True),
    p("nordlys-birch-snow", "nordlys", "Birch Snow", 8400, "Woody", "EDP", 75, 11, "#e4e1d7",
      ["Aldehydes", "Cold air accord"], ["Birch leaf", "Iris root"], ["Blonde woods", "Ambrette seed"],
      "Silver birch in a snowfield. Powdery iris and aldehydes over pale, dry woods: quiet and luminous."),
    p("nordlys-lingon", "nordlys", "Lingon", 6900, "Fresh", "EDT", 50, 16, "#c86c6c",
      ["Lingonberry", "Rhubarb"], ["Blackcurrant leaf", "Rose"], ["Moss", "Musk"],
      "Tart red berries picked in the forest understory. Rhubarb and blackcurrant leaf keep it sharp and "
      "green."),
    p("nordlys-kvist", "nordlys", "Kvist", 9200, "Woody", "EDP", 100, 7, "#8f9c7a",
      ["Pine needle", "Cypress"], ["Fir balsam", "Hay"], ["Cedarwood", "Vetiver", "Smoked tea"],
      "A walk through a pine forest after rain. Resinous fir and dry hay over cedar and a curl of smoked "
      "tea."),
    p("nordlys-midnatt", "nordlys", "Midnatt", 10800, "Chypre", "Parfum", 50, 3, "#3f4a57",
      ["Bergamot", "Black tea"], ["Oakmoss", "Violet"], ["Patchouli", "Labdanum", "Musk"],
      "A modern chypre for the white nights of midsummer: bergamot and black tea over cool violet and a "
      "dark mossy base. Only a few bottles left."),
    # Velours Noir
    p("velours-praline-noire", "velours-noir", "Praline Noire", 11800, "Gourmand", "EDP", 75, 10, "#7a4a2f",
      ["Bitter almond", "Rum"], ["Caramelised praline", "Heliotrope"], ["Vanilla bourbon", "Benzoin", "Musk"],
      "Burnt-sugar praline splashed with dark rum. Rich, lacquered and very Parisian.", True),
    p("velours-chypre-rouge", "velours-noir", "Chypre Rouge", 13500, "Chypre", "Parfum", 50, 5, "#8c1f2c",
      ["Blood orange", "Plum"], ["Rose de Mai", "Jasmine sambac"], ["Oakmoss", "Patchouli", "Ambroxan"],
      "Red lipstick and a fur stole. Plum and rose over a classic oakmoss and patchouli chypre structure, "
      "updated with clean ambroxan."),
    p("velours-tubereuse-velours", "velours-noir", "Tubéreuse Velours", 12900, "Floral", "EDP", 75, 8, "#efe0cf",
      ["Mandarin", "Green notes"], ["Tuberose absolute", "Orange blossom"], ["Suede", "Sandalwood", "Musk"],
      "An opulent tuberose wrapped in suede. Creamy, buttery and enormous: one spray fills a room."),
    p("velours-cafe-de-minuit", "velours-noir", "Café de Minuit", 9800, "Gourmand", "EDT", 100, 15, "#3b2a22",
      ["Espresso", "Cardamom"], ["Iris", "Cocoa"], ["Tonka", "Cedar"],
      "A last espresso at a zinc bar after midnight. Roasted coffee and cardamom with an iris-cocoa heart."),
    p("velours-encre", "velours-noir", "Encre", 18500, "Amber", "Parfum", 30, 2, "#1d1a24",
      ["Black pepper", "Incense"], ["Ink accord", "Violet"], ["Oud", "Ambergris accord", "Vanilla"],
      "Our most extravagant composition: ink-stained violet over oud and ambergris. A collector's parfum, "
      "made in tiny batches."),
]
