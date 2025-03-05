#!/usr/bin/env python
import numpy as np
import pylab as P
import sys
import json
import webbrowser

from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import *
from PyQt5 import QtGui, QtSql
from PyQt5.QtCore import *

from taxa_model import *
from occ_model import *
from api_thread import *
from class_synonyms import *
from edit_taxaname import *
from class_identity import *
import re
#import commons
from commons import *


def createConnection(db):
    db.setHostName("localhost")
    db.setDatabaseName("amapiac")
    db.setUserName("postgres")
    db.setPassword("postgres")
    #app2 = QApplication([])
    if not db.open():
        QMessageBox.critical(None, "Cannot open database",
                             "Unable to open database, check for connection parameters", QMessageBox.Cancel)
        return False
    return True
#
# The hist() function now has a lot more options
#
def sql_data_contribution():
    sql_txt ="""

SELECT 
	a.class_name,
	land_area, forest_area,
	(land_area - forest_area) no_forest,
	land_mining_area mining_concessions,
	land_reserve_area reserve_concessions,
	(land_mining_area-forest_mining_area) mining_noforest,
	(land_reserve_area-forest_reserve_area) reserve_noforest,
	(land_area - forest_area) - (land_mining_area-forest_mining_area) - (land_reserve_area-forest_reserve_area) land_hors_emprises,
	
	forest_mining_area forest_in_mining,
	forest_reserve_area forest_in_reserve,
	(forest_area-forest_reserve_area-forest_mining_area) forest_hors_emprises,
	
	
	
	(forest_area-forest_reserve_area-forest_mining_area) /
		(SELECT sum(a.class_value)/1E2 FROM botany_letters.massifs_properties a WHERE a.class_object = 'forest_elevation')
		forest_contrib_total,
	forest_mining_area /
		(SELECT sum(a.class_value)/1E2 FROM botany_letters.massifs_properties a WHERE a.class_object = 'forest_elevation')
		forest_in_mining_contrib_total,
	forest_reserve_area /
		(SELECT sum(a.class_value)/1E2 FROM botany_letters.massifs_properties a WHERE a.class_object = 'forest_elevation')
		forest_in_mining_contrib_total,	
	
	
	
	coalesce(
	CASE WHEN land_area>0 then
		(forest_area-forest_reserve_area-forest_mining_area) / land_area
	END, 0) forest_contrib,
	coalesce(
	CASE WHEN land_area>0 then
		(forest_mining_area) / land_area
	END, 0) forest_mining_contrib,
	coalesce(
	CASE WHEN land_area>0 then
		(forest_reserve_area) / land_area
	END, 0) forest_reserve_contrib,
	coalesce(
	CASE WHEN land_area>0 then
		forest_area/land_area
	END, 0) forest_cover
FROM
	(SELECT a.class_name, 
	COALESCE(sum(a.class_value) FILTER (WHERE a.class_object = 'forest_elevation')/1E2,0) forest_area,
	COALESCE(sum(a.class_value) FILTER (WHERE a.class_object = 'land_elevation')/1E2,0) land_area
	FROM
	botany_letters.massifs_properties a
	GROUP BY  a.class_name) a

LEFT JOIN
	(SELECT a.class_name, 
	COALESCE(sum(a.class_value) FILTER (WHERE a.class_object = 'forest_elevation')/1E2,0) forest_reserve_area,
	COALESCE(sum(a.class_value) FILTER (WHERE a.class_object = 'land_elevation')/1E2,0) land_reserve_area
	FROM
	botany_letters.reserve_properties2 a
	GROUP BY  a.class_name) b 
ON a.class_name=b.class_name
LEFT JOIN
	(SELECT a.class_name, 
	COALESCE(sum(a.class_value) FILTER (WHERE a.class_object = 'forest_elevation')/1E2,0) forest_mining_area, --,
	COALESCE(sum(a.class_value) FILTER (WHERE a.class_object = 'land_elevation')/1E2,0) land_mining_area
	FROM
	botany_letters.mining_properties2 a
	GROUP BY  a.class_name) c
ON a.class_name=c.class_name
WHERE a.class_name IS NOT NULL 
ORDER BY a.class_name


    """
    return sql_txt


#
# first create a single histogram
#
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = uic.loadUi("pn_main.ui")

# connection to the database
    db = QtSql.QSqlDatabase.addDatabase("QPSQL")

    if not createConnection(db):
        sys.exit("error")

mu, sigma = 200, 25
x = mu + sigma*P.randn(10000)
x1 = mu + sigma*P.randn(10000)
x2 = mu + sigma*P.randn(10000)

# the histogram of the data with histtype='step'
#n, bins, patches = P.hist(x, 50, histtype='stepfilled')
#P.setp(patches, 'facecolor', 'g', 'alpha', 0.75)

# add a line showing the expected distribution
#y = P.norm.pdf( bins, mu, sigma)
#l = P.plot(bins, y, 'k--', linewidth=1.5)
sql_query = sql_data_contribution()


query = QtSql.QSqlQuery (sql_query)
ls_classe = []
ls_forest_hors=[]
ls_forest_mining=[]
ls_forest_reserve=[]
ls_forest_contrib=[]
ls_forest_reserve_contrib=[]
ls_forest_mining_contrib=[]
ls_forest_hors=[]
ls_land_hors=[]
ls_mining_noforest=[]
ls_reserve_noforest=[]

while query.next():
	ls_classe.append(query.value("class_name"))
	ls_forest_contrib.append(query.value("forest_contrib"))
	ls_forest_reserve_contrib.append(query.value("forest_reserve_contrib"))
	ls_forest_mining_contrib.append(query.value("forest_mining_contrib"))
	ls_forest_hors.append(query.value("forest_hors_emprises"))
	ls_forest_mining.append(query.value("forest_in_mining"))
	ls_forest_reserve.append(query.value("forest_in_reserve"))
	ls_land_hors.append(query.value("land_hors_emprises"))
	ls_mining_noforest.append(query.value("mining_noforest"))
	ls_reserve_noforest.append(query.value("reserve_noforest"))
	
#ls_forest = tuple(ls_forest)
#print (ls_forest)
#
# create a histogram by providing the bin edges (unequally spaced)
win=P.figure()
axs = win.subplot_mosaic([['bar1', 'patches'], ['bar2', 'patches']])
yd = [x + y for x, y in zip(ls_forest_reserve_contrib, ls_forest_contrib)]
#axs['bar1'].bar(y1, ya)
axs['bar1'].bar(ls_classe,ls_forest_contrib, color='green', width = 80)
axs['bar1'].bar(ls_classe,ls_forest_reserve_contrib, color='blue', width = 80, bottom=ls_forest_contrib)
axs['bar1'].bar(ls_classe,ls_forest_mining_contrib, color='red', width = 80, bottom=yd)
#n, bins, patches = axs['bar1'].hist(ya, xa,  histtype='bar', rwidth=0.8, orientation='vertical', color = '#A52A2A')
#print (n, bins, patches)


axs['bar2'].bar(ls_classe,ls_forest_hors, color='green', width = 80)
axs['bar2'].bar(ls_classe,ls_forest_mining, color='red', width = 80, bottom=ls_forest_hors)
yd = [x + y for x, y in zip(ls_forest_reserve, ls_forest_hors)]
axs['bar2'].bar(ls_classe,ls_forest_reserve, color='blue', width = 80, bottom=yd)
yd = [x + y for x, y in zip(yd, ls_forest_reserve)]
axs['bar2'].bar(ls_classe,ls_land_hors, color='beige', width = 80, bottom=yd)
yd = [x + y for x, y in zip(yd, ls_land_hors)]
axs['bar2'].bar(ls_classe,ls_mining_noforest, color='red', width = 80, bottom=yd)
yd = [x + y for x, y in zip(yd, ls_mining_noforest)]
axs['bar2'].bar(ls_classe,ls_reserve_noforest, color='blue', width = 80, bottom=yd)


bins = [100,125,150,160,170,180,190,200,210,220,230,240,250,275,300]
# the histogram of the data with histtype='step'
#n, bins, patches = axs['bar2'].hist([x1,x2], bins,  histtype='bar', rwidth=0.8, orientation='vertical', color = ['#A52A2A','blue'], hatch=['//', 'x'])
#print (y1, n, bins, patches)
# create a new data-set
x = mu + sigma*P.randn(1000,3)
n, bins, patches = axs['patches'].hist(x, 10, histtype='bar',
                            color=['crimson', 'burlywood', 'chartreuse'],
                            label=['Crimson', 'Burlywood', 'Chartreuse'])
axs['patches'].legend(title='Fruit color')



P.show()

# #
# # now we create a cumulative histogram of the data
# #
# P.figure()

# n, bins, patches = P.hist(x, 50, histtype='bar', cumulative=True)


# # add a line showing the expected distribution
# y = P.normpdf( bins, mu, sigma).cumsum()
# y /= y[-1]
# l = P.plot(bins, y, 'k--', linewidth=1.5)



# # create a second data-set with a smaller standard deviation
# sigma2 = 15.
# x = mu + sigma2*P.randn(10000)

# n, bins, patches = P.hist(x, bins=bins, normed=1, histtype='step', cumulative=True)

# # add a line showing the expected distribution
# y = P.normpdf( bins, mu, sigma2).cumsum()
# y /= y[-1]
# l = P.plot(bins, y, 'r--', linewidth=1.5)

# # finally overplot a reverted cumulative histogram
# n, bins, patches = P.hist(x, bins=bins, normed=1,
#     histtype='step', cumulative=-1)


# P.grid(True)
# P.ylim(0, 1.05)


# #
# # histogram has the ability to plot multiple data in parallel ...
# # Note the new color kwarg, used to override the default, which
# # uses the line color cycle.
# #
# P.figure()

# # create a new data-set
# x = mu + sigma*P.randn(1000,3)

# n, bins, patches = P.hist(x, 10, normed=1, histtype='bar',
#                             color=['crimson', 'burlywood', 'chartreuse'],
#                             label=['Crimson', 'Burlywood', 'Chartreuse'])
# P.legend()

# #
# # ... or we can stack the data
# #
# P.figure()

# n, bins, patches = P.hist(x, 10, normed=1, histtype='bar', stacked=True)

# P.show()

# #
# # we can also stack using the step histtype
# #

# P.figure()

# n, bins, patches = P.hist(x, 10, histtype='step', stacked=True, fill=True)

# P.show()

# #
# # finally: make a multiple-histogram of data-sets with different length
# #
# x0 = mu + sigma*P.randn(10000)
# x1 = mu + sigma*P.randn(7000)
# x2 = mu + sigma*P.randn(3000)

# # and exercise the weights option by arbitrarily giving the first half
# # of each series only half the weight of the others:

# w0 = np.ones_like(x0)
# w0[:len(x0)/2] = 0.5
# w1 = np.ones_like(x1)
# w1[:len(x1)/2] = 0.5
# w2 = np.ones_like(x2)
# w2[:len(x2)/2] = 0.5



# P.figure()

# n, bins, patches = P.hist( [x0,x1,x2], 10, weights=[w0, w1, w2], histtype='bar')

# P.show()



# # import matplotlib as mpl
# # import matplotlib.pyplot as plt
# # import numpy as np
# # #fig1 = plt.figure(1)
# # #plt.plot(range(5),[4,3.6,2.5,3.2,4.1])
# # #fig1, axs = plt.subplots(2, 2)  # a figure with a 2x2 grid of Axes

# # mu, sigma = 115, 15
# # x = mu + sigma * np.random.randn(10000)
# # fig, ax = plt.subplots(figsize=(5, 2.7), layout='constrained')
# # # the histogram of the data
# # n, bins, patches = ax.hist(x, 50, density=True, facecolor='C0', alpha=0.75)

# # ax.set_xlabel('Length [cm]')
# # ax.set_ylabel('Probability')
# # ax.set_title('Aardvark lengths\n (not really)')
# # ax.text(75, .025, r'$\mu=115,\ \sigma=15$')
# # ax.axis([55, 175, 0, 0.03])
# # ax.grid(True)

# # plt.show()


# # plt.figure(2)
# # x = np.arange(0., 10., 0.1)
# # y1 = 2*x
# # y2 = np.sqrt(x)+6*np.log(x+1)
# # y3 = x**2-10*x
# # plt.plot(x,y1, x,y2, x,y3)

# # plt.show()
