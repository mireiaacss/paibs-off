"""
Central configuration for the PAIBS Group 10 allergen label scanner.

Everything the parser "knows" lives here so that it can be reviewed, audited
and extended without touching code:

* ALLERGENS            - the 14 EU allergens (Regulation (EU) No 1169/2011, Annex II)
                         with plain names and hidden derivatives (EN / ES, plus a
                         few FR / CA terms because Open Food Facts data is multilingual).
* FALSE_FRIENDS        - phrases that look like an allergen but are not one
                         (coconut, buckwheat, cocoa butter, lactic acid, nutmeg...).
* MAY_CONTAIN_TRIGGERS - phrases that open a precautionary "may contain" clause.
* AMBIGUOUS_TERMS      - vague ingredients that trigger the "When in doubt, warn" rule.
* ADDITIVES            - E-number risk dictionary with plain-language explanations.
* OFF_TAG_TO_ALLERGEN  - Open Food Facts allergen tags -> our canonical keys.

All terms are written naturally (with accents); the parser normalises both the
label text and these terms (lower-case, accents stripped) before matching.
"""

SAFETY_DISCLAIMER = (
    "⚠️ Always verify the physical packaging label. "
    "Do not rely solely on automated detection."
)

# ---------------------------------------------------------------------------
# 14 EU allergens
# ---------------------------------------------------------------------------
# key -> {label, label_es, icon, plain: [...], hidden: [...]}
#   plain  = the allergen's own name in common languages
#   hidden = derivatives / dishes / technical names a parent may not recognise
ALLERGENS = {
    "Gluten": {
        "label": "Cereals containing gluten",
        "label_es": "Gluten",
        "icon": "🌾",
        "plain": [
            "gluten", "wheat", "trigo", "barley", "cebada", "rye", "centeno",
            "oats", "oat", "avena", "blé", "froment", "orge", "seigle", "blat",
        ],
        "hidden": [
            "durum wheat semolina", "durum", "semolina", "sémola", "semoule",
            "spelt", "espelta", "escanda", "épeautre", "kamut", "triticale",
            "seitan", "couscous", "cuscús", "bulgur", "malt", "malta", "malte",
            "almidón de trigo", "wheat starch", "amidon de blé", "farro",
            "einkorn", "graham", "salvado de trigo", "wheat bran",
        ],
    },
    "Crustaceans": {
        "label": "Crustaceans",
        "label_es": "Crustáceos",
        "icon": "🦐",
        "plain": ["crustacean", "crustáceo", "crustacé"],
        "hidden": [
            "shrimp", "prawn", "gamba", "langostino", "crab", "cangrejo",
            "lobster", "langosta", "bogavante", "cigala", "krill", "camarón",
            "camarones", "crayfish", "cigalas", "crevette",
        ],
    },
    "Eggs": {
        "label": "Eggs",
        "label_es": "Huevo",
        "icon": "🥚",
        "plain": ["egg", "huevo", "œuf", "oeuf", "ou"],
        "hidden": [
            "albumin", "albúmina", "ovoalbúmina", "ovalbumin", "clara de huevo",
            "yema", "egg white", "egg yolk", "lysozyme", "lisozima", "ovomucoid",
            "mayonnaise", "mayonesa", "meringue", "merengue",
        ],
    },
    "Fish": {
        "label": "Fish",
        "label_es": "Pescado",
        "icon": "🐟",
        "plain": ["fish", "pescado", "poisson", "peix"],
        "hidden": [
            "anchovy", "anchovies", "anchoa", "boquerón", "tuna", "atún",
            "salmon", "salmón", "cod", "bacalao", "hake", "merluza", "sardine",
            "sardina", "surimi", "fish sauce", "gelatina de pescado",
            "fish gelatin", "abadejo", "pollock", "caballa", "mackerel",
        ],
    },
    "Peanuts": {
        "label": "Peanuts",
        "label_es": "Cacahuetes",
        "icon": "🥜",
        "plain": ["peanut", "cacahuete", "cacahuate", "maní", "arachide", "cacauet"],
        "hidden": ["groundnut", "arachis", "aceite de cacahuete", "peanut butter"],
    },
    "Soy": {
        "label": "Soybeans",
        "label_es": "Soja",
        "icon": "🫘",
        "plain": ["soy", "soya", "soja", "soybean"],
        "hidden": [
            "tofu", "edamame", "tempeh", "miso", "lecitina de soja",
            "soy lecithin", "tamari", "shoyu", "proteína de soja",
        ],
    },
    "Milk": {
        "label": "Milk (including lactose)",
        "label_es": "Leche",
        "icon": "🥛",
        "plain": ["milk", "leche", "lait", "llet", "dairy", "lácteo"],
        "hidden": [
            "casein", "caseína", "caseinato", "caseinato sódico", "caseinate",
            "whey", "suero lácteo", "suero lácteo en polvo", "suero de leche",
            "lactosuero", "lactosérum", "lactose", "lactosa", "lactoglobulin",
            "lactoglobulina", "lactalbumin", "lactoalbúmina", "ghee",
            "butter", "mantequilla", "beurre", "buttermilk", "cream", "nata",
            "crema de leche", "cheese", "queso", "fromage", "yogurt", "yoghurt",
            "yogur", "requesón", "kefir", "cuajada", "curd", "milk powder",
            "leche en polvo",
        ],
    },
    "Nuts": {
        "label": "Tree nuts",
        "label_es": "Frutos de cáscara",
        "icon": "🌰",
        "plain": ["nut", "tree nut", "frutos de cáscara", "frutos secos", "fruits à coque"],
        "hidden": [
            "almond", "almendra", "amande", "ametlla", "hazelnut", "avellana",
            "noisette", "walnut", "nuez", "nueces", "noix", "cashew", "anacardo",
            "pecan", "pecana", "pacana", "brazil nut", "pistachio", "pistacho",
            "macadamia", "praline", "praliné", "marzipan", "mazapán", "gianduja",
        ],
    },
    "Celery": {
        "label": "Celery",
        "label_es": "Apio",
        "icon": "🥬",
        "plain": ["celery", "apio", "céleri", "api"],
        "hidden": ["celeriac", "apionabo", "celery salt", "sal de apio", "celery seed"],
    },
    "Mustard": {
        "label": "Mustard",
        "label_es": "Mostaza",
        "icon": "🟡",
        "plain": ["mustard", "mostaza", "moutarde", "mostassa"],
        "hidden": ["sinapis", "mustard seed", "semillas de mostaza"],
    },
    "Sesame": {
        "label": "Sesame seeds",
        "label_es": "Sésamo",
        "icon": "⚪",
        "plain": ["sesame", "sésamo", "sésame", "sèsam"],
        "hidden": ["tahini", "tahina", "tahin", "ajonjolí", "gomasio", "benne"],
    },
    "Sulphites": {
        "label": "Sulphur dioxide and sulphites",
        "label_es": "Sulfitos",
        "icon": "🍷",
        "plain": [
            "sulphite", "sulfite", "sulfito", "sulphur dioxide", "sulfur dioxide",
            "dióxido de azufre", "diòxid de sofre", "anhídrido sulfuroso",
        ],
        "hidden": [
            "metabisulfito", "metabisulphite", "metabisulfite", "bisulfito",
            "bisulphite", "bisulfite",
        ],
    },
    "Lupin": {
        "label": "Lupin",
        "label_es": "Altramuces",
        "icon": "🌼",
        "plain": ["lupin", "lupine", "altramuz", "altramuces", "lupino", "tramús"],
        "hidden": ["lupin flour", "harina de altramuz"],
    },
    "Molluscs": {
        "label": "Molluscs",
        "label_es": "Moluscos",
        "icon": "🦪",
        "plain": ["mollusc", "mollusk", "molusco"],
        "hidden": [
            "mussel", "mejillón", "mejillones", "clam", "almeja", "oyster",
            "ostra", "squid", "calamar", "octopus", "pulpo", "cuttlefish",
            "sepia", "scallop", "vieira", "snail", "caracol", "berberecho",
            "cockle", "navaja", "chipirón", "moule",
        ],
    },
}

# Regex patterns (applied on normalised text) that map directly to an allergen.
# E220-E228 are the sulphite additives.
ALLERGEN_REGEX = {
    "Sulphites": [r"\be[\s\-]?22[0-8]\b"],
}

# Catalan "ou" (egg) and "api" (celery) are too short / ambiguous in other
# languages, so we only accept them when they are a whole comma-separated item.
WHOLE_ITEM_ONLY_TERMS = {"ou", "api"}

# ---------------------------------------------------------------------------
# False friends: phrases that must NOT raise an allergen alarm.
# Each phrase is masked from the text before searching for the listed allergens
# ("*" = mask for every allergen).
# ---------------------------------------------------------------------------
FALSE_FRIENDS = {
    # Coconut is not a tree nut under EU law; coconut milk is not dairy
    "coconut milk": ["Milk", "Nuts"],
    "coconut": ["Nuts"],
    "leche de coco": ["Milk", "Nuts"],
    "coco": ["Nuts"],
    # Buckwheat is gluten-free despite the name
    "buckwheat": ["Gluten"],
    "trigo sarraceno": ["Gluten"],
    "alforfón": ["Gluten"],
    "sarrasin": ["Gluten"],
    # Cocoa butter / shea butter are plant fats, not dairy
    "cocoa butter": ["Milk"],
    "cacao butter": ["Milk"],
    "manteca de cacao": ["Milk"],
    "beurre de cacao": ["Milk"],
    "shea butter": ["Milk"],
    "peanut butter": ["Milk"],     # still caught as Peanuts
    "nut butter": ["Milk"],
    "cream of tartar": ["Milk"],
    "crémor tártaro": ["Milk"],
    # Lactic acid / lactates are fermentation products, not dairy
    "lactic acid": ["Milk"],
    "ácido láctico": ["Milk"],
    "acide lactique": ["Milk"],
    "lactato": ["Milk"],
    "lactate": ["Milk"],
    # Nutmeg is a seed spice, not a tree nut
    "nutmeg": ["Nuts"],
    "nuez moscada": ["Nuts"],
    "noix de muscade": ["Nuts"],
    # Plant "milks": the plant itself is still checked separately
    "almond milk": ["Milk"],
    "oat milk": ["Milk"],
    "rice milk": ["Milk"],
    "soy milk": ["Milk"],
    "leche de almendra": ["Milk"],
    "leche de avena": ["Milk"],
    "leche de arroz": ["Milk"],
    "leche de soja": ["Milk"],
    # Other common traps
    "water chestnut": ["Nuts"],
    "butternut": ["Nuts"],
    "sin gluten": ["Gluten"],
    "gluten free": ["Gluten"],
    "gluten-free": ["Gluten"],
    "sans gluten": ["Gluten"],
    "sin lactosa": ["Milk"],
    "lactose free": ["Milk"],
    "lactose-free": ["Milk"],
}

# ---------------------------------------------------------------------------
# Precautionary allergen labelling ("may contain")
# Regex fragments on normalised (lower-case, accent-free) text.
# The clause runs from the trigger to the next sentence break.
# ---------------------------------------------------------------------------
MAY_CONTAIN_TRIGGERS = [
    r"puede contener(?: trazas)?(?: de)?",
    r"contiene trazas de",
    r"trazas de",
    r"trazas",
    r"may contain(?: traces)?(?: of)?",
    r"may also contain",
    r"contains traces of",
    r"traces of",
    r"traces",
    r"produced in a (?:factory|facility) (?:that|which) (?:also )?(?:handles|uses|processes)",
    r"made in a (?:factory|facility) (?:that|which) (?:also )?(?:handles|uses|processes)",
    r"elaborado en (?:una )?(?:fabrica|planta) que (?:tambien )?(?:utiliza|procesa|manipula|elabora)",
    r"peut contenir(?: des traces)?(?: de)?",
    r"traces eventuelles de",
    r"pot contenir(?: traces)?(?: de)?",
]

# ---------------------------------------------------------------------------
# "When in doubt, warn" - ambiguous ingredients that can hide allergens.
# pattern (regex on normalised text) -> (message, [possible allergens])
# ---------------------------------------------------------------------------
AMBIGUOUS_TERMS = {
    r"\b(?:aromas?|saborizantes?|natural flavou?r(?:ing)?s?|flavou?rings?|aromes?)\b": (
        "Unspecified flavourings can contain milk, celery or mustard derivatives.",
        ["Milk", "Celery", "Mustard"],
    ),
    r"\b(?:especias|spices?|epices)\b": (
        "Unspecified spice mixes can contain celery, mustard or sesame.",
        ["Celery", "Mustard", "Sesame"],
    ),
    r"\b(?:proteina vegetal|vegetable protein|proteina hidrolizada|hydroly[sz]ed (?:vegetable )?protein)\b": (
        "Vegetable / hydrolysed protein of unspecified source is often soy or wheat.",
        ["Soy", "Gluten"],
    ),
    r"(?<!soy )(?<!soya )(?<!sunflower )(?<!rapeseed )\b(?:lecitinas?|lecithins?|e[\s\-]?322)\b(?!\s*(?:\(|:|\[)?\s*(?:de\s+)?(?:soja|soy|soya|girasol|sunflower|tournesol|colza|rapeseed))": (
        "Lecithin of unspecified source is frequently soy lecithin.",
        ["Soy"],
    ),
    r"\b(?:almidon|amidon)\b(?!\s+(?:de\s+)?(?:trigo|ble|maiz|patata|arroz|tapioca|guisante|mais|pomme))"
    r"|(?<!wheat )(?<!maize )(?<!corn )(?<!potato )(?<!rice )(?<!tapioca )(?<!pea )\bstarch\b": (
        "Starch of unspecified source may be wheat starch.",
        ["Gluten"],
    ),
    r"\b(?:aceite vegetal|aceites vegetales|vegetable oils?|huiles? vegetales?)\b(?!\s*\()": (
        "Vegetable oil of unspecified source may include peanut oil.",
        ["Peanuts"],
    ),
    r"\bharina\b(?!\s+(?:de\s+)?[a-z])": (
        "Flour of unspecified source is usually wheat.",
        ["Gluten"],
    ),
    r"\b(?:caldo|stock|broth|bouillon)\b": (
        "Stocks and broths often contain celery.",
        ["Celery"],
    ),
}

# Simple inorganic / everyday chemicals that are clearly not allergens.
# Anything else ending in a chemical suffix is flagged as "unparsed".
KNOWN_SAFE_CHEMICALS = {
    "carbonato", "bicarbonato", "citrato", "fosfato", "difosfato", "cloruro",
    "sorbato", "benzoato", "ascorbato", "nitrito", "nitrato", "sulfato",
    "carbonate", "bicarbonate", "citrate", "phosphate", "diphosphate",
    "chloride", "sorbate", "benzoate", "ascorbate", "nitrite", "nitrate",
    "sulfate", "sulphate", "carbonates", "phosphates", "diphosphates",
    "glutamato", "glutamate", "acetato", "acetate", "tartrato", "tartrate",
    "malato", "malate", "hidroxido", "hydroxide", "oxido", "oxide",
    "dioxide", "dioxido", "silicato", "silicate", "pirofosfato",
    "pyrophosphate", "propionato", "propionate", "chocolate", "plate",
    "date", "dates", "tomate", "tomato", "aguacate", "dorado", "tostado",
    "triturado", "concentrado", "deshidratado", "rallado", "picado",
    "pasteurizado", "condensado", "refinado", "caramelizado", "ahumado",
    "glycerides", "diglycerides", "monoglycerides", "glyceride",
    "hydrolysate", "concentrate", "chocolates",
}
CHEMICAL_SUFFIX_REGEX = r"\b[a-z]{4,}(?:ato|ito|uro|ate|ite|ide)s?\b"

# ---------------------------------------------------------------------------
# E-number additives (risk dictionary, plain language, EN / ES)
# risk: "high" | "medium" | "low"
# ---------------------------------------------------------------------------
ADDITIVES = {
    "E102": {"name": "Tartrazine", "category": "Colour", "risk": "high",
             "en": "Azo dye. One of the 'Southampton six': may affect activity and attention in children; EU requires a warning label.",
             "es": "Colorante azoico. Puede afectar a la actividad y atención de los niños; requiere advertencia en la UE."},
    "E104": {"name": "Quinoline yellow", "category": "Colour", "risk": "high",
             "en": "Synthetic dye of the 'Southampton six'; linked to hyperactivity in children.",
             "es": "Colorante sintético asociado a hiperactividad infantil."},
    "E110": {"name": "Sunset yellow", "category": "Colour", "risk": "high",
             "en": "Azo dye of the 'Southampton six'; may affect attention in children.",
             "es": "Colorante azoico; puede afectar a la atención infantil."},
    "E122": {"name": "Azorubine / Carmoisine", "category": "Colour", "risk": "high",
             "en": "Azo dye of the 'Southampton six'; EU warning label required.",
             "es": "Colorante azoico; requiere advertencia en la UE."},
    "E124": {"name": "Ponceau 4R", "category": "Colour", "risk": "high",
             "en": "Azo dye of the 'Southampton six'; may trigger reactions in aspirin-sensitive people.",
             "es": "Colorante azoico; puede provocar reacciones en personas sensibles a la aspirina."},
    "E129": {"name": "Allura red", "category": "Colour", "risk": "high",
             "en": "Azo dye of the 'Southampton six'; linked to hyperactivity in children.",
             "es": "Colorante azoico asociado a hiperactividad infantil."},
    "E120": {"name": "Carmine / Cochineal", "category": "Colour", "risk": "medium",
             "en": "Insect-derived red colour; rare but documented allergic reactions.",
             "es": "Colorante rojo de origen animal (insecto); puede causar alergias poco frecuentes."},
    "E150D": {"name": "Sulphite ammonia caramel", "category": "Colour", "risk": "low",
              "en": "Caramel colour made with sulphite compounds; generally considered safe at normal intake.",
              "es": "Colorante caramelo elaborado con sulfitos; generalmente seguro en cantidades normales."},
    "E171": {"name": "Titanium dioxide", "category": "Colour", "risk": "high",
             "en": "Whitening agent banned in EU food since 2022 over genotoxicity concerns; may appear on imported products.",
             "es": "Blanqueante prohibido en alimentos en la UE desde 2022; puede aparecer en productos importados."},
    "E210": {"name": "Benzoic acid", "category": "Preservative", "risk": "medium",
             "en": "Preservative that can worsen asthma or hives in sensitive children.",
             "es": "Conservante que puede empeorar el asma o la urticaria en niños sensibles."},
    "E211": {"name": "Sodium benzoate", "category": "Preservative", "risk": "medium",
             "en": "Preservative studied together with azo dyes for hyperactivity; can trigger asthma in sensitive people.",
             "es": "Conservante asociado a hiperactividad junto con colorantes azoicos; puede desencadenar asma."},
    "E220": {"name": "Sulphur dioxide", "category": "Preservative", "risk": "high",
             "en": "Sulphite preservative - a legally declared EU allergen. Can trigger severe asthma attacks.",
             "es": "Conservante sulfito - alérgeno de declaración obligatoria en la UE. Puede desencadenar crisis asmáticas."},
    "E221": {"name": "Sodium sulphite", "category": "Preservative", "risk": "high",
             "en": "Sulphite preservative (EU allergen).", "es": "Conservante sulfito (alérgeno UE)."},
    "E222": {"name": "Sodium bisulphite", "category": "Preservative", "risk": "high",
             "en": "Sulphite preservative (EU allergen).", "es": "Conservante sulfito (alérgeno UE)."},
    "E223": {"name": "Sodium metabisulphite", "category": "Preservative", "risk": "high",
             "en": "Sulphite preservative (EU allergen).", "es": "Conservante sulfito (alérgeno UE)."},
    "E224": {"name": "Potassium metabisulphite", "category": "Preservative", "risk": "high",
             "en": "Sulphite preservative (EU allergen).", "es": "Conservante sulfito (alérgeno UE)."},
    "E226": {"name": "Calcium sulphite", "category": "Preservative", "risk": "high",
             "en": "Sulphite preservative (EU allergen).", "es": "Conservante sulfito (alérgeno UE)."},
    "E227": {"name": "Calcium bisulphite", "category": "Preservative", "risk": "high",
             "en": "Sulphite preservative (EU allergen).", "es": "Conservante sulfito (alérgeno UE)."},
    "E228": {"name": "Potassium bisulphite", "category": "Preservative", "risk": "high",
             "en": "Sulphite preservative (EU allergen).", "es": "Conservante sulfito (alérgeno UE)."},
    "E249": {"name": "Potassium nitrite", "category": "Preservative", "risk": "medium",
             "en": "Cured-meat preservative; can form nitrosamines. Limit intake for young children.",
             "es": "Conservante de embutidos; puede formar nitrosaminas. Limitar en niños pequeños."},
    "E250": {"name": "Sodium nitrite", "category": "Preservative", "risk": "medium",
             "en": "Cured-meat preservative; can form nitrosamines. Limit intake for young children.",
             "es": "Conservante de embutidos; puede formar nitrosaminas. Limitar en niños pequeños."},
    "E251": {"name": "Sodium nitrate", "category": "Preservative", "risk": "medium",
             "en": "Preservative converted to nitrite in the body; limit for young children.",
             "es": "Conservante que se transforma en nitrito; limitar en niños pequeños."},
    "E320": {"name": "BHA", "category": "Antioxidant", "risk": "medium",
             "en": "Synthetic antioxidant classified as a possible carcinogen (IARC 2B).",
             "es": "Antioxidante sintético clasificado como posible carcinógeno (IARC 2B)."},
    "E321": {"name": "BHT", "category": "Antioxidant", "risk": "medium",
             "en": "Synthetic antioxidant; under review for possible health effects.",
             "es": "Antioxidante sintético; en revisión por posibles efectos sobre la salud."},
    "E322": {"name": "Lecithins", "category": "Emulsifier", "risk": "low",
             "en": "Emulsifier. Often made from SOY - check the source if your child is soy-allergic.",
             "es": "Emulgente. Suele proceder de la SOJA - compruebe el origen si su hijo es alérgico."},
    "E330": {"name": "Citric acid", "category": "Acidity regulator", "risk": "low",
             "en": "Common acidifier; considered safe.", "es": "Acidulante común; se considera seguro."},
    "E338": {"name": "Phosphoric acid", "category": "Acidity regulator", "risk": "low",
             "en": "Acidifier used in colas; high intake linked to lower bone density.",
             "es": "Acidulante de refrescos de cola; un consumo alto se asocia a menor densidad ósea."},
    "E407": {"name": "Carrageenan", "category": "Thickener", "risk": "medium",
             "en": "Seaweed thickener; may irritate the gut in sensitive people. Not allowed in infant formula in some uses.",
             "es": "Espesante de algas; puede irritar el intestino en personas sensibles."},
    "E471": {"name": "Mono- and diglycerides of fatty acids", "category": "Emulsifier", "risk": "low",
             "en": "Emulsifier; can be of animal or plant origin. Marker of ultra-processed food.",
             "es": "Emulgente de origen animal o vegetal; indicador de alimento ultraprocesado."},
    "E621": {"name": "Monosodium glutamate", "category": "Flavour enhancer", "risk": "medium",
             "en": "Flavour enhancer; some people report headaches or flushing. Marker of ultra-processed food.",
             "es": "Potenciador del sabor; algunas personas refieren dolor de cabeza. Indicador de ultraprocesado."},
    "E951": {"name": "Aspartame", "category": "Sweetener", "risk": "high",
             "en": "Sweetener classified as possibly carcinogenic (IARC 2B, 2023). Dangerous for people with phenylketonuria.",
             "es": "Edulcorante clasificado como posible carcinógeno (IARC 2B, 2023). Peligroso en fenilcetonuria."},
    "E500": {"name": "Sodium carbonates (baking soda)", "category": "Raising agent", "risk": "low",
             "en": "Common raising agent; considered safe.", "es": "Gasificante común; se considera seguro."},
    "E950": {"name": "Acesulfame K", "category": "Sweetener", "risk": "medium",
             "en": "Artificial sweetener; not recommended for young children.",
             "es": "Edulcorante artificial; no recomendado para niños pequeños."},
    "E955": {"name": "Sucralose", "category": "Sweetener", "risk": "medium",
             "en": "Artificial sweetener; not recommended for young children.",
             "es": "Edulcorante artificial; no recomendado para niños pequeños."},
}

# Additives named in words rather than E-numbers (normalised text -> E-number)
ADDITIVE_NAME_ALIASES = {
    "tartrazina": "E102", "tartrazine": "E102",
    "amarillo ocaso": "E110", "sunset yellow": "E110",
    "azorrubina": "E122", "carmoisine": "E122",
    "rojo allura": "E129", "allura red": "E129",
    "dioxido de titanio": "E171", "titanium dioxide": "E171",
    "benzoato sodico": "E211", "benzoato de sodio": "E211", "sodium benzoate": "E211",
    "dioxido de azufre": "E220", "sulphur dioxide": "E220", "sulfur dioxide": "E220",
    "metabisulfito sodico": "E223", "sodium metabisulphite": "E223",
    "nitrito sodico": "E250", "nitrito de sodio": "E250", "sodium nitrite": "E250",
    "glutamato monosodico": "E621", "monosodium glutamate": "E621",
    "aspartamo": "E951", "aspartame": "E951",
    "sucralosa": "E955", "sucralose": "E955",
    "carragenano": "E407", "carrageenan": "E407",
    "acido fosforico": "E338", "phosphoric acid": "E338",
}

# ---------------------------------------------------------------------------
# Open Food Facts allergen tags -> canonical keys
# ---------------------------------------------------------------------------
OFF_TAG_TO_ALLERGEN = {
    "en:gluten": "Gluten",
    "en:crustaceans": "Crustaceans",
    "en:eggs": "Eggs",
    "en:fish": "Fish",
    "en:peanuts": "Peanuts",
    "en:soybeans": "Soy",
    "en:milk": "Milk",
    "en:nuts": "Nuts",
    "en:celery": "Celery",
    "en:mustard": "Mustard",
    "en:sesame-seeds": "Sesame",
    "en:sulphur-dioxide-and-sulphites": "Sulphites",
    "en:lupin": "Lupin",
    "en:molluscs": "Molluscs",
}
ALLERGEN_TO_OFF_TAG = {v: k for k, v in OFF_TAG_TO_ALLERGEN.items()}

OFF_USER_AGENT = "PAIBS-Group10-AllergenScanner/0.2 (ESADE student prototype)"
OFF_TIMEOUT_SECONDS = 8
