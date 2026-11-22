# GRI Standards Database

GRI_STANDARDS = {
    "GRI 201": {
        "title": "Economic Performance",
        "keywords": ["direct economic value", "distributed", "retained earnings", "financial implications", "climate change risks", "benefit plan"],
        "required_metrics": ["revenues", "operating costs", "wages", "benefits"]
    },
    "GRI 302": {
        "title": "Energy",
        "keywords": ["energy consumption", "fuel consumption", "renewable energy", "energy intensity", "energy reduction", "electricity", "heating", "cooling"],
        "required_metrics": ["joules", "mwh", "kwh", "gigajoules"]
    },
    "GRI 303": {
        "title": "Water and Effluents",
        "keywords": ["water withdrawal", "water discharge", "water consumption", "water stress", "freshwater", "groundwater"],
        "required_metrics": ["megaliters", "cubic meters", "gallons", "liters"]
    },
    "GRI 304": {
        "title": "Biodiversity",
        "keywords": ["protected areas", "biodiversity", "habitats", "iucn red list", "species", "conservation"],
        "required_metrics": ["hectares", "species count", "km2"]
    },
    "GRI 305": {
        "title": "Emissions",
        "keywords": ["scope 1", "scope 2", "scope 3", "ghg emissions", "co2", "methane", "ozone-depleting", "nitrogen oxides", "sox"],
        "required_metrics": ["metric tons co2e", "tco2e", "tonnes"]
    },
    "GRI 306": {
        "title": "Waste",
        "keywords": ["waste generation", "waste diversion", "hazardous waste", "landfill", "recycling", "incineration"],
        "required_metrics": ["metric tons", "tonnes", "kg"]
    },
    "GRI 401": {
        "title": "Employment",
        "keywords": ["new hires", "turnover", "parental leave", "benefits", "full-time"],
        "required_metrics": ["rate", "number", "percentage"]
    },
    "GRI 403": {
        "title": "Occupational Health and Safety",
        "keywords": ["injuries", "ill-health", "hazards", "management system", "incident rate", "lost time"],
        "required_metrics": ["rate", "number of fatalities"]
    },
    "GRI 404": {
        "title": "Training and Education",
        "keywords": ["training hours", "skills upgrading", "transition assistance", "employee development"],
        "required_metrics": ["hours", "average"]
    },
    "GRI 405": {
        "title": "Diversity and Equal Opportunity",
        "keywords": ["governance bodies", "diversity", "gender", "age group", "minority", "equal remuneration"],
        "required_metrics": ["percentage", "ratio"]
    },
    "GRI 413": {
        "title": "Local Communities",
        "keywords": ["local communities", "impact assessments", "development programs", "engagement"],
        "required_metrics": ["percentage", "operations"]
    }
}

BIAS_FLUFF_WORDS = [
    "proud", "committed", "dedicated", "believe", "vision", "mission", 
    "strive", "aim", "aspire", "world-class", "journey", "bolder", 
    "unwavering", "industry-leading", "best-in-class", "cutting-edge",
    "passion", "core to our", "dna", "deeply"
]
