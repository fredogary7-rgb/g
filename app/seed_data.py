"""Données initiales (produits Fanta).

NOTE IMPORTANTE (incohérence documentée) :
Pour "Fanta 2", le calcul réel 980 x 35 = 34 300 FCFA, alors que la valeur
fournie est 32 100 FCFA. Les deux valeurs restent configurables : la valeur
affichée/stockée par défaut est celle qui a été fournie (32 100 FCFA).
Vous pourrez la corriger depuis l'admin -> Produits si vous le souhaitez.
"""

PRODUCTS_SEED = [
    {
        "name": "Fanta 2",
        "price": 8000,
        "daily_income": 980,
        # 980 x 35 = 34 300 : la valeur fournie (32 100) est conservée telle quelle.
        "total_income": 32100,
        "duration": 35,
        "image": "fa.JPG",
        "sort_order": 1,
        "description": "Pack Fanta Agrumes — formule intermédiaire.",
    },
    {
        "name": "Fanta 3",
        "price": 15000,
        "daily_income": 1600,
        "total_income": 56000,
        "duration": 35,
        "image": "fa1.JPG",
        "sort_order": 2,
        "description": "Pack Fanta Citron — rendement renforcé.",
    },
    {
        "name": "Fanta 4",
        "price": 20000,
        "daily_income": 2100,
        "total_income": 73500,
        "duration": 35,
        "image": "fa2.JPG",
        "sort_order": 3,
        "description": "Pack Fanta Exotique — profil équilibré.",
    },
    {
        "name": "Fanta 5",
        "price": 30000,
        "daily_income": 3400,
        "total_income": 119000,
        "duration": 35,
        "image": "fa3.JPG",
        "sort_order": 4,
        "description": "Pack Fanta Ananas — croissance solide.",
    },
    {
        "name": "Fanta 6",
        "price": 50000,
        "daily_income": 5900,
        "total_income": 206500,
        "duration": 35,
        "image": "fa4.JPG",
        "sort_order": 5,
        "description": "Pack Fanta Fraise — rendement avancé.",
    },
    {
        "name": "Fanta 7",
        "price": 80000,
        "daily_income": 8900,
        "total_income": 311500,
        "duration": 35,
        "image": "fa5.JPG",
        "sort_order": 6,
        "description": "Pack Fanta Tropical — performance élevée.",
    },
    {
        "name": "Fanta 8",
        "price": 100000,
        "daily_income": 12000,
        "total_income": 420000,
        "duration": 35,
        "image": "fa6.JPG",
        "sort_order": 7,
        "description": "Pack Fanta Premium — formule la plus rentable.",
    },
]

