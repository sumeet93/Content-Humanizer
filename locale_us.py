#!/usr/bin/env python3
"""US-spelling normalizer (British -> US), whole-word + case-preserving.
Curated/safe list with word boundaries, so it never touches proper nouns, standard
codes, or substrings like 'diameter'/'parameter'. Use it when a document is for a
US audience and you want consistent US orthography.

Usage:
    python3 locale_us.py <file1.md> [file2.md ...]       # rewrites in place, reports changes
Importable:
    from locale_us import normalize; text = normalize(text)
Or via the humanizer:
    python3 humanize_doc.py in.md out.md --us-spelling
"""
import sys, re

# British -> US (curated; whole-word matches only). Longer forms are covered by \b anyway.
PAIRS = [
    ("customise","customize"),("customised","customized"),("customising","customizing"),
    ("customisable","customizable"),("customisation","customization"),
    ("optimise","optimize"),("optimised","optimized"),("optimising","optimizing"),("optimisation","optimization"),
    ("analyse","analyze"),("analysed","analyzed"),("analysing","analyzing"),("analyser","analyzer"),
    ("sulphur","sulfur"),("sulphuric","sulfuric"),("sulphide","sulfide"),("sulphates","sulfates"),("sulphate","sulfate"),
    ("catalogue","catalog"),("catalogues","catalogs"),("catalogued","cataloged"),
    ("colour","color"),("colours","colors"),("coloured","colored"),("colouring","coloring"),
    ("behaviour","behavior"),("behaviours","behaviors"),
    ("favour","favor"),("favours","favors"),("favourable","favorable"),("favoured","favored"),
    ("organisation","organization"),("organisations","organizations"),("organise","organize"),
    ("organised","organized"),("organising","organizing"),
    ("standardise","standardize"),("standardised","standardized"),("standardisation","standardization"),
    ("prioritise","prioritize"),("prioritised","prioritized"),
    ("minimise","minimize"),("minimised","minimized"),("maximise","maximize"),("maximised","maximized"),
    ("utilise","utilize"),("utilised","utilized"),("utilising","utilizing"),
    ("centre","center"),("centres","centers"),("centred","centered"),
    ("fibre","fiber"),("fibres","fibers"),
    ("litre","liter"),("litres","liters"),
    ("metre","meter"),("metres","meters"),
    ("millimetre","millimeter"),("millimetres","millimeters"),
    ("centimetre","centimeter"),("centimetres","centimeters"),
    ("moulded","molded"),("mould","mold"),("moulding","molding"),
    ("grey","gray"),
    ("licence","license"),("defence","defense"),("offence","offense"),
    ("programme","program"),("programmes","programs"),
    ("aluminium","aluminum"),
    ("ageing","aging"),
    ("modelling","modeling"),("modelled","modeled"),
    ("labelled","labeled"),("labelling","labeling"),("labour","labor"),
    ("fulfil","fulfill"),("fulfilment","fulfillment"),("enrol","enroll"),
    ("dependant","dependent"),("licence","license"),
    ("vapour","vapor"),("vapours","vapors"),("odour","odor"),("odours","odors"),
    ("neighbour","neighbor"),("neighbours","neighbors"),("neighbouring","neighboring"),
    ("neighbourhood","neighborhood"),("neighbourhoods","neighborhoods"),("marvellous","marvelous"),
    ("practise","practice"),  # verb -> US noun/verb spelling
    ("enquiry","inquiry"),("enquiries","inquiries"),
    ("kerb","curb"),
    ("specialise","specialize"),("specialised","specialized"),("specialising","specializing"),
    ("recognise","recognize"),("recognised","recognized"),
    ("emphasise","emphasize"),("emphasised","emphasized"),
    ("pressurise","pressurize"),("pressurised","pressurized"),("pressurising","pressurizing"),
    ("depressurise","depressurize"),("depressurised","depressurized"),
    ("galvanise","galvanize"),("galvanised","galvanized"),
]

def _case(word, repl):
    if word.isupper(): return repl.upper()
    if word[0].isupper(): return repl[0].upper()+repl[1:]
    return repl

_COMPILED = [(re.compile(r"\b"+re.escape(b)+r"\b", re.I), b, u) for b,u in PAIRS]

def normalize(t):
    for rx,_b,u in _COMPILED:
        t = rx.sub(lambda m: _case(m.group(0), u), t)
    return t

def normalize_report(t):
    hits = {}
    for rx,b,u in _COMPILED:
        n = len(rx.findall(t))
        if n: hits[b]=n
    return normalize(t), hits

if __name__ == "__main__":
    total = {}
    for f in sys.argv[1:]:
        s = open(f).read()
        out, hits = normalize_report(s)
        if hits:
            open(f,"w").write(out)
            for k,v in hits.items(): total[k]=total.get(k,0)+v
            print(f"{f}: {sum(hits.values())} fixed {dict(hits)}")
    if total:
        print("TOTAL:", dict(sorted(total.items(), key=lambda x:-x[1])))
    else:
        print("no British spellings found")
