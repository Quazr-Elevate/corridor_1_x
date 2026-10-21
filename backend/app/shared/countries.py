"""ISO 3166-1 country codes.

The API stores alpha-2 codes everywhere (``IN``, ``AE``). Inputs are
lenient: alpha-3 codes (``IND``) and common English names (``India``,
``UAE``) are mapped to alpha-2 so older clients/rows keep working.

A frozen copy of this table lives in
``alembic/versions/0019_business_entity.py`` (migrations must not import
app code that may change later).
"""
from __future__ import annotations

# (alpha-2, alpha-3, English short name)
COUNTRIES: tuple[tuple[str, str, str], ...] = (
    ("AF", "AFG", "Afghanistan"), ("AX", "ALA", "Aland Islands"), ("AL", "ALB", "Albania"),
    ("DZ", "DZA", "Algeria"), ("AS", "ASM", "American Samoa"), ("AD", "AND", "Andorra"),
    ("AO", "AGO", "Angola"), ("AI", "AIA", "Anguilla"), ("AQ", "ATA", "Antarctica"),
    ("AG", "ATG", "Antigua and Barbuda"), ("AR", "ARG", "Argentina"), ("AM", "ARM", "Armenia"),
    ("AW", "ABW", "Aruba"), ("AU", "AUS", "Australia"), ("AT", "AUT", "Austria"),
    ("AZ", "AZE", "Azerbaijan"), ("BS", "BHS", "Bahamas"), ("BH", "BHR", "Bahrain"),
    ("BD", "BGD", "Bangladesh"), ("BB", "BRB", "Barbados"), ("BY", "BLR", "Belarus"),
    ("BE", "BEL", "Belgium"), ("BZ", "BLZ", "Belize"), ("BJ", "BEN", "Benin"),
    ("BM", "BMU", "Bermuda"), ("BT", "BTN", "Bhutan"), ("BO", "BOL", "Bolivia"),
    ("BQ", "BES", "Bonaire, Sint Eustatius and Saba"), ("BA", "BIH", "Bosnia and Herzegovina"),
    ("BW", "BWA", "Botswana"), ("BV", "BVT", "Bouvet Island"), ("BR", "BRA", "Brazil"),
    ("IO", "IOT", "British Indian Ocean Territory"), ("BN", "BRN", "Brunei Darussalam"),
    ("BG", "BGR", "Bulgaria"), ("BF", "BFA", "Burkina Faso"), ("BI", "BDI", "Burundi"),
    ("CV", "CPV", "Cabo Verde"), ("KH", "KHM", "Cambodia"), ("CM", "CMR", "Cameroon"),
    ("CA", "CAN", "Canada"), ("KY", "CYM", "Cayman Islands"), ("CF", "CAF", "Central African Republic"),
    ("TD", "TCD", "Chad"), ("CL", "CHL", "Chile"), ("CN", "CHN", "China"),
    ("CX", "CXR", "Christmas Island"), ("CC", "CCK", "Cocos (Keeling) Islands"), ("CO", "COL", "Colombia"),
    ("KM", "COM", "Comoros"), ("CG", "COG", "Congo"), ("CD", "COD", "Congo, Democratic Republic of the"),
    ("CK", "COK", "Cook Islands"), ("CR", "CRI", "Costa Rica"), ("CI", "CIV", "Cote d'Ivoire"),
    ("HR", "HRV", "Croatia"), ("CU", "CUB", "Cuba"), ("CW", "CUW", "Curacao"),
    ("CY", "CYP", "Cyprus"), ("CZ", "CZE", "Czechia"), ("DK", "DNK", "Denmark"),
    ("DJ", "DJI", "Djibouti"), ("DM", "DMA", "Dominica"), ("DO", "DOM", "Dominican Republic"),
    ("EC", "ECU", "Ecuador"), ("EG", "EGY", "Egypt"), ("SV", "SLV", "El Salvador"),
    ("GQ", "GNQ", "Equatorial Guinea"), ("ER", "ERI", "Eritrea"), ("EE", "EST", "Estonia"),
    ("SZ", "SWZ", "Eswatini"), ("ET", "ETH", "Ethiopia"), ("FK", "FLK", "Falkland Islands"),
    ("FO", "FRO", "Faroe Islands"), ("FJ", "FJI", "Fiji"), ("FI", "FIN", "Finland"),
    ("FR", "FRA", "France"), ("GF", "GUF", "French Guiana"), ("PF", "PYF", "French Polynesia"),
    ("TF", "ATF", "French Southern Territories"), ("GA", "GAB", "Gabon"), ("GM", "GMB", "Gambia"),
    ("GE", "GEO", "Georgia"), ("DE", "DEU", "Germany"), ("GH", "GHA", "Ghana"),
    ("GI", "GIB", "Gibraltar"), ("GR", "GRC", "Greece"), ("GL", "GRL", "Greenland"),
    ("GD", "GRD", "Grenada"), ("GP", "GLP", "Guadeloupe"), ("GU", "GUM", "Guam"),
    ("GT", "GTM", "Guatemala"), ("GG", "GGY", "Guernsey"), ("GN", "GIN", "Guinea"),
    ("GW", "GNB", "Guinea-Bissau"), ("GY", "GUY", "Guyana"), ("HT", "HTI", "Haiti"),
    ("HM", "HMD", "Heard Island and McDonald Islands"), ("VA", "VAT", "Holy See"),
    ("HN", "HND", "Honduras"), ("HK", "HKG", "Hong Kong"), ("HU", "HUN", "Hungary"),
    ("IS", "ISL", "Iceland"), ("IN", "IND", "India"), ("ID", "IDN", "Indonesia"),
    ("IR", "IRN", "Iran"), ("IQ", "IRQ", "Iraq"), ("IE", "IRL", "Ireland"),
    ("IM", "IMN", "Isle of Man"), ("IL", "ISR", "Israel"), ("IT", "ITA", "Italy"),
    ("JM", "JAM", "Jamaica"), ("JP", "JPN", "Japan"), ("JE", "JEY", "Jersey"),
    ("JO", "JOR", "Jordan"), ("KZ", "KAZ", "Kazakhstan"), ("KE", "KEN", "Kenya"),
    ("KI", "KIR", "Kiribati"), ("KP", "PRK", "North Korea"), ("KR", "KOR", "South Korea"),
    ("KW", "KWT", "Kuwait"), ("KG", "KGZ", "Kyrgyzstan"), ("LA", "LAO", "Laos"),
    ("LV", "LVA", "Latvia"), ("LB", "LBN", "Lebanon"), ("LS", "LSO", "Lesotho"),
    ("LR", "LBR", "Liberia"), ("LY", "LBY", "Libya"), ("LI", "LIE", "Liechtenstein"),
    ("LT", "LTU", "Lithuania"), ("LU", "LUX", "Luxembourg"), ("MO", "MAC", "Macao"),
    ("MG", "MDG", "Madagascar"), ("MW", "MWI", "Malawi"), ("MY", "MYS", "Malaysia"),
    ("MV", "MDV", "Maldives"), ("ML", "MLI", "Mali"), ("MT", "MLT", "Malta"),
    ("MH", "MHL", "Marshall Islands"), ("MQ", "MTQ", "Martinique"), ("MR", "MRT", "Mauritania"),
    ("MU", "MUS", "Mauritius"), ("YT", "MYT", "Mayotte"), ("MX", "MEX", "Mexico"),
    ("FM", "FSM", "Micronesia"), ("MD", "MDA", "Moldova"), ("MC", "MCO", "Monaco"),
    ("MN", "MNG", "Mongolia"), ("ME", "MNE", "Montenegro"), ("MS", "MSR", "Montserrat"),
    ("MA", "MAR", "Morocco"), ("MZ", "MOZ", "Mozambique"), ("MM", "MMR", "Myanmar"),
    ("NA", "NAM", "Namibia"), ("NR", "NRU", "Nauru"), ("NP", "NPL", "Nepal"),
    ("NL", "NLD", "Netherlands"), ("NC", "NCL", "New Caledonia"), ("NZ", "NZL", "New Zealand"),
    ("NI", "NIC", "Nicaragua"), ("NE", "NER", "Niger"), ("NG", "NGA", "Nigeria"),
    ("NU", "NIU", "Niue"), ("NF", "NFK", "Norfolk Island"), ("MK", "MKD", "North Macedonia"),
    ("MP", "MNP", "Northern Mariana Islands"), ("NO", "NOR", "Norway"), ("OM", "OMN", "Oman"),
    ("PK", "PAK", "Pakistan"), ("PW", "PLW", "Palau"), ("PS", "PSE", "Palestine"),
    ("PA", "PAN", "Panama"), ("PG", "PNG", "Papua New Guinea"), ("PY", "PRY", "Paraguay"),
    ("PE", "PER", "Peru"), ("PH", "PHL", "Philippines"), ("PN", "PCN", "Pitcairn"),
    ("PL", "POL", "Poland"), ("PT", "PRT", "Portugal"), ("PR", "PRI", "Puerto Rico"),
    ("QA", "QAT", "Qatar"), ("RE", "REU", "Reunion"), ("RO", "ROU", "Romania"),
    ("RU", "RUS", "Russia"), ("RW", "RWA", "Rwanda"), ("BL", "BLM", "Saint Barthelemy"),
    ("SH", "SHN", "Saint Helena, Ascension and Tristan da Cunha"), ("KN", "KNA", "Saint Kitts and Nevis"),
    ("LC", "LCA", "Saint Lucia"), ("MF", "MAF", "Saint Martin (French part)"),
    ("PM", "SPM", "Saint Pierre and Miquelon"), ("VC", "VCT", "Saint Vincent and the Grenadines"),
    ("WS", "WSM", "Samoa"), ("SM", "SMR", "San Marino"), ("ST", "STP", "Sao Tome and Principe"),
    ("SA", "SAU", "Saudi Arabia"), ("SN", "SEN", "Senegal"), ("RS", "SRB", "Serbia"),
    ("SC", "SYC", "Seychelles"), ("SL", "SLE", "Sierra Leone"), ("SG", "SGP", "Singapore"),
    ("SX", "SXM", "Sint Maarten (Dutch part)"), ("SK", "SVK", "Slovakia"), ("SI", "SVN", "Slovenia"),
    ("SB", "SLB", "Solomon Islands"), ("SO", "SOM", "Somalia"), ("ZA", "ZAF", "South Africa"),
    ("GS", "SGS", "South Georgia and the South Sandwich Islands"), ("SS", "SSD", "South Sudan"),
    ("ES", "ESP", "Spain"), ("LK", "LKA", "Sri Lanka"), ("SD", "SDN", "Sudan"),
    ("SR", "SUR", "Suriname"), ("SJ", "SJM", "Svalbard and Jan Mayen"), ("SE", "SWE", "Sweden"),
    ("CH", "CHE", "Switzerland"), ("SY", "SYR", "Syria"), ("TW", "TWN", "Taiwan"),
    ("TJ", "TJK", "Tajikistan"), ("TZ", "TZA", "Tanzania"), ("TH", "THA", "Thailand"),
    ("TL", "TLS", "Timor-Leste"), ("TG", "TGO", "Togo"), ("TK", "TKL", "Tokelau"),
    ("TO", "TON", "Tonga"), ("TT", "TTO", "Trinidad and Tobago"), ("TN", "TUN", "Tunisia"),
    ("TR", "TUR", "Turkey"), ("TM", "TKM", "Turkmenistan"), ("TC", "TCA", "Turks and Caicos Islands"),
    ("TV", "TUV", "Tuvalu"), ("UG", "UGA", "Uganda"), ("UA", "UKR", "Ukraine"),
    ("AE", "ARE", "United Arab Emirates"), ("GB", "GBR", "United Kingdom"), ("US", "USA", "United States"),
    ("UM", "UMI", "United States Minor Outlying Islands"), ("UY", "URY", "Uruguay"),
    ("UZ", "UZB", "Uzbekistan"), ("VU", "VUT", "Vanuatu"), ("VE", "VEN", "Venezuela"),
    ("VN", "VNM", "Vietnam"), ("VG", "VGB", "Virgin Islands (British)"), ("VI", "VIR", "Virgin Islands (U.S.)"),
    ("WF", "WLF", "Wallis and Futuna"), ("EH", "ESH", "Western Sahara"), ("YE", "YEM", "Yemen"),
    ("ZM", "ZMB", "Zambia"), ("ZW", "ZWE", "Zimbabwe"),
)

ALPHA2: frozenset[str] = frozenset(a2 for a2, _, _ in COUNTRIES)
ALPHA3_TO_ALPHA2: dict[str, str] = {a3: a2 for a2, a3, _ in COUNTRIES}

# Common alternative spellings seen in free-text "country" fields.
_ALIASES: dict[str, str] = {
    "uae": "AE",
    "u.a.e.": "AE",
    "emirates": "AE",
    "usa": "US",
    "u.s.a.": "US",
    "united states of america": "US",
    "uk": "GB",
    "u.k.": "GB",
    "great britain": "GB",
    "england": "GB",
    "bharat": "IN",
    "korea": "KR",
    "republic of korea": "KR",
    "russian federation": "RU",
    "viet nam": "VN",
    "türkiye": "TR",
    "turkiye": "TR",
    "czech republic": "CZ",
    "ivory coast": "CI",
    "holland": "NL",
    "the netherlands": "NL",
}
NAME_TO_ALPHA2: dict[str, str] = {name.lower(): a2 for a2, _, name in COUNTRIES} | _ALIASES


def to_alpha2(value: str | None) -> str | None:
    """Best-effort conversion of an alpha-2 / alpha-3 code or an English
    name to an alpha-2 code. ``None`` when it can't be recognised."""
    if value is None:
        return None
    v = value.strip()
    if not v:
        return None
    up = v.upper()
    if len(up) == 2 and up in ALPHA2:
        return up
    if len(up) == 3 and up in ALPHA3_TO_ALPHA2:
        return ALPHA3_TO_ALPHA2[up]
    return NAME_TO_ALPHA2.get(v.lower())
