class rowtable(object):
    dict_rang =  {0 : 'Unknown', 10 : 'Family', 14 : 'Genus', 21 : 'Species', 22 : 'Subspecies', 23 : 'Variety'}
    def __init__(self, idtaxonref, taxaname, authors, idrang, taxascore = 0):
        self.authors = authors
        self.taxa_name = taxaname
        self.id_rang = idrang
        self.id_taxon_ref = idtaxonref
        self.taxa_score = taxascore

    @property
    def rank_txt (self):
        try :
            txt_rk = rowtable.dict_rang[self.id_rang]
        except :
            txt_rk = rowtable.dict_rang[0]   
        return txt_rk
        
    @property
    def columnCount(self):
        return 3
    @property
    def status(self):
        return self.taxa_score
        # if self.taxa_score > 0 and self.taxa_score < 1:
        #     return 2
        # else:
        #     return self.taxa_score


class TaxaName(rowtable):
    def __init__(self, taxarow):
        super(TaxaName, self).__init__()