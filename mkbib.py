import subprocess, glob, os.path, sys, getopt
import re
import csv
import string
import nltk
from sklearn.feature_extraction.text import CountVectorizer
from pybtex.database import parse_file, BibliographyData
from ordered_set import OrderedSet
from inspect import getsourcefile

def lemmatize_list(sl):
    lsl = [wnl.lemmatize(s) for s in sl]
    return lsl

def lemmatize_string(s):
    sl = s.split()
    lsl = lemmatize_list(sl)
    return ' '.join(lsl)

def tokenize(name):
    tokens = OrderedSet(analyzer(name)).items

    tokens = lemmatize_list(tokens)

    i = 0;
    while i < len(tokens):
        if tokens[i] in dumb_words or tokens[i].isdigit():
            tokens.pop(i)
        else:
            i += 1

    return tokens

def acronym(ts):
    if 1 == len(ts):
        return ts[0]

    acron = ''
    for t in ts:
        if t in known_acronyms:
            acron += t
        else:
            acron += t[0]
    return acron

def query_acronym_dict(ts):
    tss = set(ts)
    for k, v in acronym_dict.items():
        ks = set(k.split())
        if ks.issubset(tss):
            return v

    return None

def usage():
    print 'Usage: python %s PATH' % (sys.argv[0])
    print 'Normalize and generate helm-bibtex aware .bib file.\n'

wnl = nltk.WordNetLemmatizer()

vectorizer = CountVectorizer(stop_words='english')
analyzer = vectorizer.build_analyzer()

pattern = re.compile(r"[\(\{](.+?)[\)\}]")

match_thresh = 0.75

dir_name  = os.path.dirname(getsourcefile(lambda:0))

book_fields = {}
acronym_dict = {}
known_acronyms = set()
dumb_words = set()

with open(os.path.join(dir_name, 'book_fields.csv'), 'rb') as f:
    reader = csv.reader(f)
    for row in reader:
        book_fields[row[0].lower()] = row[1].lower()

with open(os.path.join(dir_name, 'known_acronyms.csv'), 'rb') as f:
    reader = csv.reader(f)
    for row in reader:
        known_acronyms.add(row[0].lower())

with open(os.path.join(dir_name, 'dumb_words.csv'), 'rb') as f:
    reader = csv.reader(f)
    for row in reader:
        dumb_words.add(wnl.lemmatize(row[0].lower()))

with open(os.path.join(dir_name, 'acronym_dict.csv'), 'rb') as f:
    reader = csv.reader(f)
    for row in reader:
        acronym_dict[' '.join(tokenize(row[0].lower()))] = row[1].lower()

try:
    opts, args = getopt.getopt(sys.argv[1:], "")
except getopt.GetoptError as err:
    print str(err)
    usage()
    sys.exit(2)

if 1 != len(args):
    usage()
    sys.exit()

cwd = os.getcwd()
os.chdir(args[0])
if os.path.exists('tmp.bib'):
    os.remove('tmp.bib')

subprocess.call("cat *.bib > tmp.bib", shell=True)

bib_data = parse_file('tmp.bib').lower()

pdf_paths = glob.glob(os.path.join(args[0], '*.pdf'))
pdf_names = [os.path.basename(s) for s in pdf_paths]
pdf_names = [s[s.find(')')+1:s.find('.pdf')] for s in pdf_names]
pdf_names_tokens = [set(tokenize(s)) for s in pdf_names]

new_bib_data = BibliographyData()
for k, v in bib_data.entries.items():
    if book_fields[v.type] in v.fields.keys():
        book_name = v.fields[book_fields[v.type]].lower()

        book_name_tokens = tokenize(book_name)

        book_name_acronym = query_acronym_dict(book_name_tokens)

        if not book_name_acronym:
            inter = set(book_name_tokens) & known_acronyms
            if 1 == len(inter):
                book_name_acronym = inter.pop()

        if not book_name_acronym:
            parens = re.findall(pattern, book_name)

            i = 0
            while i < len(parens) and not book_name_acronym:
                book_name_acronym = acronym(tokenize(parens[i]))
                i += 1

        if not book_name_acronym:
            book_name_acronym = acronym(book_name_tokens)
    else:
        book_name_acronym = ''

    if 'year' in v.fields.keys():
        book_name_acronym += v.fields['year'][2:4]

    new_key = book_name_acronym + '/'
    for i, p in enumerate(v.persons['author']):
        if 0 == i:
            new_key += p.last_names[0].encode().translate(string.maketrans('',''),string.punctuation)
        else:
            new_key += p.last_names[0].encode().translate(string.maketrans('',''),string.punctuation)[0]

    overlap = 0
    title_tokens = set(tokenize(v.fields['title']))
    for i, t in enumerate(pdf_names_tokens):
        inter = title_tokens & t
        if len(inter) > overlap:
            overlap = len(inter)
            match = i
    if overlap * 1.0 / len(title_tokens) >= match_thresh:
        v.fields['file'] = pdf_paths[match]

    new_bib_data.entries[new_key] = v

new_bib_data.to_file('_'.join(os.path.split(os.getcwd())[1].split())+'.bib', 'bibtex')

os.remove('tmp.bib')
