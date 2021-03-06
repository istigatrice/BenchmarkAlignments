# supporter functions for checking datasets
import yaml
import logging
import datetime
import urllib2
from Bio.Nexus import Nexus
from Bio import SeqUtils
import itertools

def add_alignment(aln, result):
    result["n_taxa"] = aln.ntax
    result["n_sites"] = aln.nchar
    result["n_datablocks"] = len(aln.charpartitions["loci"])

    # get GC skew
    aln_seq = ''.join([str(x) for x in aln.matrix.values()])
    gc = SeqUtils.GC(aln_seq)

    # ACGT proportions
    A = float(aln_seq.count('A'))
    T = float(aln_seq.count('T'))
    G = float(aln_seq.count('G'))
    C = float(aln_seq.count('C'))
    sum_count = A + T + G + C



    # gaps
    gaps = float(aln_seq.count('?') + aln_seq.count('-') + aln_seq.count('N'))
    gap_proportion = gaps/float(len(aln_seq))

    result["gc_proportion"] = gc
    result["gap_proportion"] = gap_proportion
    result["a_proportion"] = A/sum_count
    result["c_proportion"] = C/sum_count
    result["g_proportion"] = G/sum_count
    result["t_proportion"] = T/sum_count

    return result

def check_alignment(alignment_file):
    # do lots of checks on an alignment
    aln = Nexus.Nexus()
    try:
        aln.read(alignment_file)
    except Exception as e:
        logging.error("Couldn't read nexus file, please check and try again.")
        logging.error("Here's the error from the BioPython Nexus.Nexus module")
        logging.error(e)
        raise ValueError

    # Check that there are just two charpartitions: 'loci' and 'genomes'
    if aln.charpartitions.keys() != ['loci', 'genomes']:
        logging.error("There should be exactly two CHARPARTITIONS: 'loci' and 'genomes'. Check and try again.")    
        raise ValueError

    # Check for an 'outgroup' taxset
    if aln.taxsets.keys() != ['outgroups']:
        logging.error("There should be exactly one TAXSET: 'outgroups'. Check and try again.")    
        raise ValueError

    # Check that no sites are duplicated in either charpartition
    all_sites = set(range(aln.nchar))

    loci_sites = [x[1] for x in aln.charpartitions['loci'].items()]
    loci_sites = list(itertools.chain.from_iterable(loci_sites))

    if len(loci_sites) > len(all_sites):
        logging.error("The loci charpartition has %d more site(s) than the number of sites in the alignment" %(len(loci_sites) - len(all_sites)))    
        raise ValueError


    geno_sites = [x[1] for x in aln.charpartitions['genomes'].items()]
    geno_sites = list(itertools.chain.from_iterable(geno_sites))

    if len(geno_sites) > len(all_sites):
        logging.error("The genomes charpartition has %d more site(s) than the number of sites in the alignment" %(len(geno_sites) - len(all_sites)))    
        raise ValueError


    # Check that all sites are covered by 'loci' charpartition
    if len(set(loci_sites)) < len(all_sites):
        logging.error("The loci charpartition does not cover the following sites, please fix: %s" %(all_sites.difference(set(loci_sites))))    
        raise ValueError


    # Check that all sites are covered by 'genomes' charpartition
    if len(set(geno_sites)) < len(all_sites):
        logging.error("The genomes charpartition does not cover the following sites, please fix: %s" %(all_sites.difference(set(geno_sites))))    
        raise ValueError

    return(aln)

def add_yaml(yaml_file, result):

    y = yaml.load(open(yaml_file, 'r'))

    result["study_DOI"]         =  y['study']['DOI']
    result["study_year"]        =  y['study']['year']
    result["dataset_DOI"]       =  y['dataset']['DOI']
    result["license"]           =  y['dataset']['license']
    result["root_age_timetree_mya"] =  y['dataset']['timetree root age'].rstrip(' mya')
    result["root_age_study_mya"]    =  y['dataset']['study root age'].rstrip(' mya')
    result["clade_latin"]       =  y['dataset']['study clade']['latin']
    result["clade_english"]     =  y['dataset']['study clade']['english']
    result["taxon_ID"]          =  y['dataset']['study clade']['taxon ID']

    return(result)

def check_yaml(yaml_file):

    y = yaml.load(open(yaml_file, 'r'))

    # Basic structure of the file
    if set(y.keys()) != set(['study', 'dataset']): 
        logging.error("Missing 'study' or 'dataset' section from your yaml file")
        raise ValueError

    if set(y["study"].keys()) != set(['DOI', 'reference', 'year']):
        logging.error("The sections of your 'study' section should be 'reference', 'year', and 'DOI'")
        raise ValueError

    if set(y["dataset"].keys()) != set(['DOI', 'license', 'used for tree inference', 'notes', 'study clade', 'timetree root age', 'study root age']):
        logging.error("The sections of your 'dataset' section should be 'DOI', 'license', 'used for tree inference', 'notes', 'study clade', 'timetree root age', 'study root age'")
        raise ValueError

    if set(y["dataset"]["study clade"].keys()) != set(['english', 'latin', 'taxon ID']):
        logging.error("The sections of your 'study clade' section should be 'english', 'latin', 'taxon ID'")
        raise ValueError

    # Check values one by one
    check_url("".join(["http://", y['study']['DOI']]))
    check_reference(y['study']['reference'])
    check_year(y['study']['year'])

    dataset_url = y['dataset']['DOI']
    if dataset_url != 'NA':
        check_url("".join(["http://", y['dataset']['DOI']]))

    check_license(y['dataset']['license'])
    check_tree(y['dataset']['used for tree inference'])

    check_age(y['dataset']['timetree root age'])
    check_age(y['dataset']['study root age'])

    check_clade(y['dataset']['study clade'])    

def check_clade(clade):

    if isinstance(clade['latin'], basestring) == False:
        logging.error("The latin clade must be a string")
        raise ValueError

    if isinstance(clade['english'], basestring) == False:
        logging.error("The latin clade must be a string")
        raise ValueError

    if isinstance(clade['taxon ID'], int) == False:
        logging.error("The taxon ID must be a number")
        raise ValueError

    tax_url = "".join(['http://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=', str(clade['taxon ID'])])
    check_url(tax_url)

def check_age(age):
    # nothing is OK
    if age == "NA":
        return(0)

    if len(age.split())>2:
        logging.error("There's a problem with this age: %s. It should be 'x mya', where x is a number", age)
        raise ValueError

    try:
        t = float(age.split()[0])
    except:
        logging.error("Check the study/timetree root age (%s). It looks like it's not a number" % age.split()[0])
        raise ValueError

    mya = age.split()[1]

    min = 0.0
    max = 3000.0 # unlikley to have ages > 3000mya!!

    if t > max or t < min:
        logging.error("Check the study/timetree root age. It's too big or too small")
        raise ValueError

    if mya != "mya":
        logging.error("The number in the study/root age should be followed by 'mya' as units. Check and try again.")
        raise ValueError


def check_tree(text):
    if text != True:
        logging.error("The 'used for tree inference' section must be 'yes'. Otherwise we don't want the dataset")
        logging.error("Yours is: '%s'", text)
        raise ValueError


def check_license(license):

    # if it's not CC0, it needs an explanation
    if license == "CC0":
        pass
    else:
        logging.error("The license for the dataset must be CC0")
        raise ValueError


def check_url(url):
    try: 
        urllib2.urlopen(url)
    except urllib2.URLError as e:
        logging.error("There was a URLError: %r" % e)
        logging.error("This URL didn't work: %s" % url)
    except socket.timeout as e:
        logging.error("The url timed out. Check and try again please!")
        logging.error("The error was: %r" %e)
        logging.error("This URL didn't work: %s" % url)

def check_reference(text):
    if len(text) < 10:
        logging.error("Your reference looks too short (<10 characters) check and fix it.")
        raise ValueError

def check_year(year):
    
    if isinstance(year, int) == False:
        logging.error("Check the study year. It's not a number.")
        raise ValueError

    # the year might be next year (pulications are odd), and it's unlikely to be <1950...
    max = datetime.datetime.now().year + 1
    min = 1950

    if year > max or year < min:
        logging.error("Check the study year (%d). It's too big or too small" % year)
        raise ValueError
