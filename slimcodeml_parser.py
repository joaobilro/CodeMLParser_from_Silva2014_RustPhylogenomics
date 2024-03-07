#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  codeml_parser.py
#  
#  Copyright 2014 Diogo N. Silva
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#  
#  

import os
import locale
import argparse
from collections import OrderedDict
import statsmodels.sandbox.stats.multicomp as multi_correction
from scipy.stats import chi2


parser = argparse.ArgumentParser(description="This edited version of codeml_parser is a python 3 script that was"
											"developed to parse the output of  multiple branch site model results"
											"from PAML and performs chi-square test of significance.")

parser.add_argument("-in", dest="folder_list", nargs="+", required=True, help="The list of the directories containing the output "
																			"of the branch site model")

parser.add_argument("--clade", "-c", dest="clade", nargs="*", choices = ["pucciniales_genome", "pucciniales"], help="For clade specific statistics, provide the taxa "
																"members"
															"of such clade separated by whitespace: 'pucciniales_genome' or 'pucciniales'")
parser.add_argument("-o", dest="output_file", help="Provide the name for the output file, .csv format")

parser.add_argument("-p", dest="csv_options", nargs="*", choices=["a"], help="CSV options: a - Conserved"
																				"trends across clade and other taxa")

parser.add_argument("-w", dest="write_alignments", action="store_const", const=True, help="Use this option if you want"
																						"to write the gap-free "
																						"alignments used by codeml")

arg = parser.parse_args()


class PamlPair ():
	""" This class contains the information for a given pair of Null/Alternative analyses from the PAML branch site
	model. It contains all the relevant information about that single pair. If the gene's pair was identified under
	positive selection by LRT, then several attributes related to positive selection findings will be available """

	def __init__(self, folder):
		""" To instantiate a PamlPair object, a folder containing the Null and Alternative sub folders is required """

		# Initialize p-value attribute
		self.pvalue = None
		self.fdr_value = None

		# Initialize likelihood attributes
		self.alternative_lnL = None
		self.null_lnL = None

		# A status attribute to escape possible errors
		self.status = True

		# Initialize aa filter attributes
		self.conserved_aa = None
		self.unique_aa = None
		self.diverse_aa = None
		self.all_clade_unique = None
		self.mostly_unique = None
		self.mostly_diverse = None
		self.mostly_conserved = None
		self.conserved_aa_list = None
		self.unique_aa_list = None
		self.diverse_aa_list = None
		self.mostly_conserved_aa_list = None
		self.most_common_aa = None
		self.all_conserved = None
		self.all_mostly_conserved = None
		self.shared = None
		self.shared_aa_list = None
		self.variable = None
		self.variable_aa_list = None

		# Set folder variable
		self.folder = folder

		# The arguments of the following function are the specific substring of the codeml output file and it may be
		# changed to conform to the output file names. Also, they do not need to be the same.
		self.__parse_main_alternative__(".mlc")
		self.__parse_main_null__(".mlc")

	def set_fdr(self, fdr):
		""" Update the pvalue """
		self.fdr_value = fdr

	def __parse_main_alternative__(self, file_suffix, subfolder="/Alternative"):
		""" This function parses the main output file of the alternative model, setting a number of object attributes.
		By default the output files of the alternative hypothesis are assumed to be inside a folder named
		"Alternative", but this can be changed using the subfolder argument.

		A list of attributes follows:
		- self.gene_length : (int) The length of the gene (gene length is 0 is alignment is non-existent);
		- self.alternative_lnL : (str) The likelihood of the alternative model;
		- self.selected_aa: (list) A list of tuples, with each element containing the position of the aa and the PP
		associated with it;
		- self.conserved_prop : (tuple) A tuple containing the proportion, background w value, foreground w value for
		the conserved w class;
		- self.neutral_prop : (tuple) A tuple containing the proportion, background w value, foreground w value for
		the neutral w class;
		- self.high_selection_prop : (tuple) A tuple containing the proportion, background w value, foreground w
		value for the w class with positive selection on the foreground branch and negative selection on the background
		branch;
		- self.selection_prop : (tuple) A tuple containing the proportion, background w value, foreground w value for
		the w class with positive selection on the foreground branch and neutral selection on the background branch;
		"""

		# Assuming that the output files of the alternative hypothesis are inside a folder named "Alternative",
		# this will find the codeml output file based on a specific substring (file_suffix)
		folder_contents = os.listdir(self.folder + subfolder)
		file_path = self.folder + subfolder + "/" + "".join([x for x in folder_contents if file_suffix in x])

		# If the output file does not exist, set the status for this Pair object to false and return
		if file_path == self.folder + subfolder:
			self.status = False
			return 1

		# Opening output file
		try:
			file_handle = open(file_path)
		except:
			print("Cannot open file %s" % file_path)
			raise SystemExit

		# Creating variable that will store the alignment
		self.alignment = OrderedDict()
		counter, alignment_counter, fall_back_alignment_counter = 0, 0, 0
		self.selected_aa = []

		for line in file_handle:
			if line.strip().startswith("seed used = "):
				fall_back_alignment_counter = 1
				# Getting preliminary gene length. If the alignment is not reduced due to gaps, this gene_length
				# variable will be used. Otherwise it will be replaced by the gap free alignment length
				gene_length_str = next(file_handle)

				if gene_length_str.strip() != "":
					self.gene_length = gene_length_str.strip().split()[1]

			if line.strip().startswith("Before deleting alignment gaps"):
				fall_back_alignment_counter = 0

			# Getting the gene length
			if line.strip().startswith("After deleting gaps."):
				self.gene_length = int("".join([x for x in line if x.isdigit()]))

			# Getting the likelihood of the model
			if line.strip().startswith("lnL"):
				self.alternative_lnL = float(line.split(":")[-1].split()[0])

			# Getting the proportion of sites for each class
			if line.strip().startswith("proportion"):
				proportion_vals = line.split()[1:]
				proportion_vals = [float(x) for x in proportion_vals]

			# Getting the background w values
			if line.strip().startswith("background w"):
				background_w = line.split()[2:]
				background_w = [float(x) for x in background_w]

			# Getting the foreground w values
			if line.strip().startswith("foreground w"):
				foreground_w = line.split()[2:]
				foreground_w = [float(x) for x in foreground_w]

			if line.strip().startswith("Bayes Empirical Bayes (BEB)"):
				counter = 1
				next(file_handle)

			# Reset alignment counter
			if counter == 1 and line.strip().startswith("The grid"):
				counter = 0

			# Reset fall_back_alignment counter
			if fall_back_alignment_counter == 1 and line.strip().startswith("Printing out site pattern counts"):
				fall_back_alignment_counter = 0

			# Getting selected aminoacid position and PP value
			if counter == 1 and line.strip() != "":
				aa = line.split()
				if "*" in aa[-1]:
					self.selected_aa.append((aa[0], aa[-1]))  # aa[0]: position of the aa; aa[-1] the PP value of
					# positive selection

			if line.strip().startswith("After deleting gaps"):

				# In case the cleaned alignment is empty
				if " 0 sites" not in line:
					alignment_counter = 1
				else:
					self.gene_length = 0

			if line.strip().startswith("Printing out site pattern counts"):
				alignment_counter = 0

			# Populating alignment attribute
			if len(line.split("_")) != 1 and alignment_counter == 1:

				fields = line.strip().split()
				species = fields[0]
				sequence = fields[1:]

				self.alignment[species] = sequence

			if len(line.split("_")) != 1 and fall_back_alignment_counter == 1 and self.alignment != {}:

				fields = line.strip().split()
				species = fields[0]
				sequence = fields[1:]

				self.alignment[species] = sequence

			if len(line.split("_")) != 1 and fall_back_alignment_counter == 1 and alignment_counter == 0:
				fields = line.strip().split()
				species = fields[0]
				sequence = fields[1:]

				self.alignment[species] = sequence

		else:

			try:
				# Assigning proportions and w values to object attributes
				self.conserved_prop = (proportion_vals[0], background_w[0], foreground_w[0])  # The list contains
				# [proportion, background_w, foreground_w] for the w class 0
				self.neutral_prop = (proportion_vals[1], background_w[1], foreground_w[1])
				self.high_selection_prop = (proportion_vals[2], background_w[2], foreground_w[2])
				self.selection_prop = (proportion_vals[3], background_w[3], foreground_w[3])
			except NameError:
				pass

		file_handle.close()

	def __parse_main_null__(self, file_suffix, subfolder="/Null"):
		""" This function parses the main output file of the null model, setting a number of object attributes.
		By default the output files of the null hypothesis are assumed to be inside a folder named "Null",
		but this can be changed using the subfolder argument.

		A list of attributes follows:
		self.null_lnL : (str) The likelihood of the alternative model;
		"""

		# Assuming that the output files of the null hypothesis are inside a folder named "Null",
		# this will find the codeml output file based on a specific substring (file_suffix)
		folder_contents = os.listdir(self.folder + subfolder)
		file_path = self.folder + subfolder + "/" + "".join([x for x in folder_contents if file_suffix in x])

		# If the output file does not exist, set the status for this Pair object to false and return
		if file_path == self.folder + subfolder:
			self.status = False
			return 1

		try:
			file_handle = open(file_path)
		except:
			print("Cannot open file %s" % file_path)
			raise SystemExit

		for line in file_handle:

			if line.strip().startswith("lnL"):
				# Getting the likelihood
				self.null_lnL = float(line.split(":")[-1].split()[0])

		file_handle.close()

	def likelihood_ratio_test(self):
		""" Conducts a likelihood ratio test of the self.alternative_lnL and self.null_lnL values and returns a float
		with the p-value. It returns the chi2 p-value and also sets it as an object attribute: self.lrt_pvalue """

		# In case one of the likelihood values does not exist in one of the files, set p-value as 1. This indicates a
		#  problem somewhere in the analysis of this pair and therefore I attributed a non significant p-value
		if self.alternative_lnL is None or self.null_lnL is None:
			self.pvalue = 1.0
			return

		lrt = 2 * (self.alternative_lnL - self.null_lnL)

		# If the LRT value is below 0, there is something wrong since a null hypothesis with less parameters should
		# not have a higher likelihood than the alternative hypothesis. This usually means that there was some
		# convergence problems in the alternative test.
		if lrt < 0:
			self.pvalue = 1.0
			return

		# Calculating chi-square test using scipy.stats
		df = 1		## df = 1 for the branch-site models lrt
		self.pvalue = float(1 - chi2(df).cdf(lrt))  

	def filter_aa(self, clade, set_aa_columns=True):
		""" This function returns a number of selected amino acid filters, such as conserved, unique or diversifying
		amino acids. A clade of species must be provided and the number of unique and diversifying selected amino
		acids to that clade will be returned. If there are positively selected sites, this will set a number of
		attributes for each site class, otherwise it will return a "NA" string

		The set_aa_columns option can be set to True, so that the function also sets, for each site class, a list
		containing the entire alignment column. This allows nucleotide/codon trends in the data set but decreases
		speed."""

		def detect_unique_aa(alignment, taxa_list):
			""" Returns the number of unique and exclusive amino acids of a given clade, irrespective of the presence
			of selection """
			aa_count = 0

			# Alignment sanity check
			if len(alignment) > 0 and len(list(alignment.values())[0]) > 0:

				for i in range(len(list(alignment.values())[0])):
					taxa_specific_aa = [codon_table[char[i]] for sp, char in alignment.items() if sp in taxa_list]
					other_taxa_aa = [codon_table[char[i]] for sp, char in alignment.items() if sp not in taxa_list]

					if len(set(taxa_specific_aa)) == 1 and taxa_specific_aa[0] not in set(other_taxa_aa):
						aa_count += 1

			return aa_count

		def detect_conserved_aa(alignment, taxa_list):
			""" Returns a tuple of sets containing all conserved and mostly conserved codons in the clade group,
			excluding the selected positions """

			all_conserved = []
			all_mostly_conserved = []

			# Alignment sanity check
			if len(alignment) > 0 and len(list(alignment.values())[0]) > 0:

				for i in range(len(list(alignment.values())[0])):

					if i not in selected_positions:
						column = [codon_table[char[i]] for sp, char in alignment.items()]
						most_common_aa = [x for x in set(column) if all([column.count(x) >= column.count(y) for y in
																		set(column)])]
						most_common_aa_frequency = float(column.count(most_common_aa[0])) / float(len(column))

						# For the strictly conserved
						if len(set(column)) == 1:

							clade_codons = [char[i] for sp, char in alignment.items() if sp in taxa_list]
							other_codons = [char[i] for sp, char in alignment.items() if sp not in taxa_list]
							all_conserved.append((clade_codons, other_codons))

						# For the mostly conserved
						if most_common_aa_frequency > 0.70:

							clade_codons = [char[i] for sp, char in alignment.items() if sp in taxa_list]
							other_codons = [char[i] for sp, char in alignment.items() if sp not in taxa_list]
							all_mostly_conserved.append((clade_codons, other_codons))

			return all_conserved, all_mostly_conserved

		# List of preset clades
		preset_dic = {"pucciniales_genome": ["Puccinia_triticina", "Melampsora_laricis_populina",
											"Puccinia_graminis"], "pucciniales": ["Puccinia_triticina",
											"Melampsora_laricis_populina", "Puccinia_graminis", "Hemileia_vastatrix"]}

		# Inspecting if a preset clade is to be used
		for preset in preset_dic:
			if [preset] == clade:
				clade = preset_dic[preset]
				clade = [x for x in clade if x in self.alignment]
	
		codon_table = {
					'ATA': 'I', 'ATC': 'I', 'ATT': 'I', 'ATG': 'M',
					'ACA': 'T', 'ACC': 'T', 'ACG': 'T', 'ACT': 'T',
					'AAC': 'N', 'AAT': 'N', 'AAA': 'K', 'AAG': 'K',
					'AGC': 'S', 'AGT': 'S', 'AGA': 'R', 'AGG': 'R',
					'CTA': 'L', 'CTC': 'L', 'CTG': 'L', 'CTT': 'L',
					'CCA': 'P', 'CCC': 'P', 'CCG': 'P', 'CCT': 'P',
					'CAC': 'H', 'CAT': 'H', 'CAA': 'Q', 'CAG': 'Q',
					'CGA': 'R', 'CGC': 'R', 'CGG': 'R', 'CGT': 'R',
					'GTA': 'V', 'GTC': 'V', 'GTG': 'V', 'GTT': 'V',
					'GCA': 'A', 'GCC': 'A', 'GCG': 'A', 'GCT': 'A',
					'GAC': 'D', 'GAT': 'D', 'GAA': 'E', 'GAG': 'E',
					'GGA': 'G', 'GGC': 'G', 'GGG': 'G', 'GGT': 'G',
					'TCA': 'S', 'TCC': 'S', 'TCG': 'S', 'TCT': 'S',
					'TTC': 'F', 'TTT': 'F', 'TTA': 'L', 'TTG': 'L',
					'TAC': 'Y', 'TAT': 'Y', 'TAA': '_', 'TAG': '_',
					'TGC': 'C', 'TGT': 'C', 'TGA': '_', 'TGG': 'W'}

		selected_positions = [int(pos[0]) - 1 for pos in self.selected_aa]

		# Check if there are any selected aa in this pair
		if self.selected_aa is not []:

			# Simple numerical attributes of the object
			self.conserved_aa, self.unique_aa, self.diverse_aa, self.all_clade_unique, self.mostly_conserved, \
			self.mostly_unique, self.mostly_diverse, self.shared, self.variable = 0, 0, 0, 0, 0, 0, 0, 0, 0

			if set_aa_columns is True:
				# More complex attributes containing lists of tuples
				self.conserved_aa_list = []
				self.unique_aa_list = []
				self.diverse_aa_list = []
				self.mostly_conserved_aa_list = []
				self.shared_aa_list = []
				self.variable_aa_list = []

			# Starting the iteration over the selected amino acids to sort them into classes
			for aminoacid in self.selected_aa:
				position = int(aminoacid[0]) -1 # The position of the aa in the alignment
				aa_column = [codon_table[char[position]] for char in self.alignment.values()]  ## The complete column for sites under selection from the alignment
				unique_aa_colum = set(aa_column)  ## Creates a list of the aa's present in the column, in spite of frequencies
				self.most_common_aa = [x for x in unique_aa_colum if all([aa_column.count(x) >= aa_column.count(y)  ## List of the most common aa's for each column of interest
																		for y in unique_aa_colum])]
				
				# Check if there is only one variant
				if len(unique_aa_colum) == 1:
					self.conserved_aa += 1

					if set_aa_columns is True and clade is not None:
						clade_codon_list = [char[position] for sp, char in self.alignment.items() if sp in clade]
						other_codon_list = [char[position] for sp, char in self.alignment.items() if sp not in clade]
						self.conserved_aa_list.append((clade_codon_list, other_codon_list))

					continue
				
				if clade is not None:
					clade_specific_aa = [codon_table[char[position]] for sp, char in self.alignment.items() if sp in clade]
					other_aa = [codon_table[char[position]] for sp, char in self.alignment.items() if sp not in clade]

					# Counts the number of positively selected sites exclusive and homogeneous to the given clade
					if len(set(clade_specific_aa)) == 1 and clade_specific_aa[0] not in other_aa:
						self.unique_aa += 1
						continue

					# Counts the number of positively selected sites exclusive but with variation within a given clade
					elif not [x for x in clade_specific_aa if x in other_aa]:
						self.diverse_aa += 1
						continue

					elif self.most_common_aa is not [] and [x for x in clade_specific_aa if clade_specific_aa.count(x) > other_aa.count(x)]:
						if len(set(clade_specific_aa)) == 1 and clade_specific_aa[0] not in self.most_common_aa:
							self.mostly_unique += 1
							continue
						if not [x for x in clade_specific_aa if x in self.most_common_aa]:
							self.mostly_diverse += 1
							continue

				# Check if the most common aa is also mostly prevalent. This will add to the mostly conserved class,
				# which relaxes the conserved_aa variant by allowing a small percentage of sites to mutate. Threshold
				# is hardcoded at 0.50
				# Shared is a class that represents aminoacids that are shared between the specific clade and other 
				# species, but are represented at below the .50 cutoff. There can only be 2 aa in the clade group
				# Variable is a class that represents aminoacids that do not follow any of the previous criteria
				if self.most_common_aa:
					frequency_most_common_aa = float(aa_column.count(self.most_common_aa[0])) / float(len(aa_column))

					if frequency_most_common_aa >= 0.50 and len(set(clade_specific_aa)) == 1 and clade_specific_aa[0] in self.most_common_aa:
						self.mostly_conserved += 1

						if set_aa_columns is True:
							clade_codon_list = [char[position] for sp, char in self.alignment.items() if sp in clade]
							other_codon_list = [char[position] for sp, char in self.alignment.items() if sp not in clade]
							self.mostly_conserved_aa_list.append((clade_codon_list, other_codon_list))
						continue
  
					elif frequency_most_common_aa >= 0.50 and len(set(clade_specific_aa)) == 2 and any(x in clade_specific_aa for x in self.most_common_aa):
						self.shared +=1 

						if set_aa_columns is True:
							clade_codon_list = [char[position] for sp, char in self.alignment.items() if sp in clade]
							other_codon_list = [char[position] for sp, char in self.alignment.items() if sp not in clade]
							self.shared_aa_list.append((clade_codon_list, other_codon_list))
						continue
  
					else: 
						self.variable +=1 	


			self.all_clade_unique = detect_unique_aa(self.alignment, clade)

			# This will inspect all alignment columns and will be more time consuming
			if set_aa_columns is True:

				self.all_conserved, self.all_mostly_conserved = detect_conserved_aa(self.alignment, clade)

		else:
			return "NA"


class PamlPairSet ():
	""" This class will contain a variable number of PamlPair objects and will provide a number of methods for their
	analyses """

	def __init__(self, folder_list):
		""" The object is initialized with a folder list, each of which contains both the Null and Alternative model
		folders, which will be used to create the PamlPair object. The PamlPair objects will be stored in a dictionary
		with their corresponding folder (gene name) as a key """

		# Initialize get_number_aa attributes
		self.R = None
		self.L = None
		self.S = None

		# Initialize get_class_proportion attributes
		self.class_proportions = None

		self.paml_pairs = OrderedDict()

		for folder in folder_list:
			print("\rProcessing folder %s out of %s (%s)" % (folder_list.index(folder)+1, len(folder_list), folder)),

			paml_object = PamlPair(folder)

			# This will ensure that only valid pair objects are processed
			if paml_object.status is True:

				self.paml_pairs[folder] = PamlPair(folder)

	def pair_list(self):
		""" Returns a list with the PamlPair objects """

		return [val for val in self.paml_pairs.values()]

	def test_selection_suite(self):
		""" Wrapper for the basic selection test and FDR correction """

		self.test_selection()
		self.fdr_correction()

	def write_alignments(self):
		""" Writes the actual alignments used in codeml, i.e., without gaps, in Fasta format """

		for gene, pair in self.paml_pairs.items():
			output_handle = open(gene + ".fas", "w")
			for sp, seq in pair.alignment.items():
				output_handle.write(">%s\n%s\n" % (sp, "".join(seq)))
			output_handle.close()

	def get_number_aa(self):
		""" Prints the number of mostly conserved sites for the R,S and L amino acids """

		self.R, self.L, self.S = 0, 0, 0

		for gene, pair in self.paml_pairs.items():
			if pair.fdr_value < 0.05:
				if pair.mostly_conserved:
					try:
						most_common = "".join(pair.most_common_aa).strip()
						if most_common == "S":
							self.S += 1
						if most_common == "R":
							self.R += 1
						if most_common == "L":
							self.L += 1
					except:
						continue

		print("S: %s, L: %s, R: %s" % (self.S, self.L, self.R))

	def test_selection(self):
		""" For each PamlPair object in the self.paml_pairs conduct a likelihood ratio test for positive selection """

		for pair in self.paml_pairs.values():
			print("\rProcessing selection tests on file %s of %s (%s)" % (list(self.paml_pairs.values()).index(pair)+1,
																		len(self.paml_pairs.values()), pair.folder)),

			pair.likelihood_ratio_test()

	def get_class_proportion(self):
		""" Sets the number of genes that contain a given site class as new attributes """

		self.class_proportions = {"conserved": 0, "mostly_conserved": 0, "unique": 0, "diversifying": 0,
								"mostly_unique": 0, "mostly_diverse": 0, "shared": 0, "variable": 0}
		selected_genes = 0

		for pair in self.paml_pairs.values():

			if pair.conserved_aa is not None and pair.conserved_aa > 0 and pair.fdr_value < 0.05:
				self.class_proportions["conserved"] += 1

			if pair.mostly_conserved is not None and pair.mostly_conserved > 0 and pair.fdr_value < 0.05:
				self.class_proportions["mostly_conserved"] += 1

			if pair.unique_aa is not None and pair.unique_aa > 0 and pair.fdr_value < 0.05:
				self.class_proportions["unique"] += 1

			if pair.diverse_aa is not None and pair.diverse_aa > 0 and pair.fdr_value < 0.05:
				self.class_proportions["diversifying"] += 1

			if pair.mostly_unique is not None and pair.mostly_unique > 0 and pair.fdr_value < 0.05:
				self.class_proportions["mostly_unique"] += 1

			if pair.mostly_diverse is not None and pair.mostly_diverse > 0 and pair.fdr_value < 0.05:
				self.class_proportions["mostly_diverse"] += 1

			if pair.shared is not None and pair.shared > 0 and pair.fdr_value < 0.05:
				self.class_proportions["shared"] += 1
    
			if pair.variable is not None and pair.variable > 0 and pair.fdr_value < 0.05:
				self.class_proportions["variable"] += 1

			if pair.fdr_value < 0.05:
				selected_genes += 1

		for key, val in self.class_proportions.items():
			self.class_proportions[key] = float(val) / float(selected_genes)

	def get_gene_class_proportions(self):
		""" For each gene, get the proportion of sites for each site class """

		gene_storage = OrderedDict()  # Order of the list elements [conserved, mostly conserved, unique, diversifying, shared, variable]

		for gene, pair in self.paml_pairs.items():
			if pair.fdr_value < 0.05:
				if pair.selected_aa:
					number_selected_aa = float(len(pair.selected_aa))

					conserved_proportion = float(pair.conserved_aa) / number_selected_aa
					mostly_conserved_proportion = float(pair.mostly_conserved) / number_selected_aa
					unique_proportion = (float(pair.unique_aa) + float(pair.mostly_unique)) / number_selected_aa
					diversifying_proportion = (float(pair.diverse_aa) + float(pair.mostly_diverse)) / number_selected_aa
					shared_proportion = (float(pair.shared)) / number_selected_aa
					variable_proportion = (float(pair.variable)) / number_selected_aa

					gene_storage[gene] = [conserved_proportion + mostly_conserved_proportion, unique_proportion,
										diversifying_proportion, shared_proportion, variable_proportion]

		output_file = open("Gene_class_proportion.csv", "w")

		output_file.write("Gene; Conserved; Unique; Diversifying; Shared; Variable\n")

		for gene, vals in gene_storage.items():
			output_file.write("%s; %s; %s; %s; %s; %s\n" % (gene, vals[0], vals[1], vals[2], vals[3], vals[4]))

		output_file.close()

	def fdr_correction(self, alpha=0.05):
		""" Applies a False Discovery Rate correction to the p-values of the PamlPair objects """

		pvalue_dict = OrderedDict()

		for gene, pair in self.paml_pairs.items():
			if pair.pvalue is not None:
				pvalue_dict[gene] = pair.pvalue

		pvalue_list = [pval for pval in pvalue_dict.values()]

		fdr_bool_list, fdr_pvalue_list, alpha_s, alpha_b = multi_correction.multipletests(pvalue_list, alpha=alpha,
																				method="fdr_bh")

		# Updating PamlPairs with corrected p-value
		for gene, fdr_val in zip(pvalue_dict, fdr_pvalue_list):
			self.paml_pairs[gene].set_fdr(fdr_val)
  
	def filter_aa(self, clade, set_aa_columns=None):
		""" A wrapper that applies the filter_aa method of the PamlPair to every pair """

		for gene, pair in self.paml_pairs.items():
			pair.filter_aa(clade, set_aa_columns=set_aa_columns)

	def check_trend_conserve(self):
		""" This method can only be applied after the filter_aa method. It parses all codon columns of the conserved
		and mostly conserved sites to check for a trend in codon/nucleotide usage """

		codon_table = {
    	'ATA': 'I', 'ATC': 'I', 'ATT': 'I', 'ATG': 'M',
		'ACA': 'T', 'ACC': 'T', 'ACG': 'T', 'ACT': 'T',
		'AAC': 'N', 'AAT': 'N', 'AAA': 'K', 'AAG': 'K',
		'AGC': 'S', 'AGT': 'S', 'AGA': 'R', 'AGG': 'R',
		'CTA': 'L', 'CTC': 'L', 'CTG': 'L', 'CTT': 'L',
		'CCA': 'P', 'CCC': 'P', 'CCG': 'P', 'CCT': 'P',
		'CAC': 'H', 'CAT': 'H', 'CAA': 'Q', 'CAG': 'Q',
		'CGA': 'R', 'CGC': 'R', 'CGG': 'R', 'CGT': 'R',
		'GTA': 'V', 'GTC': 'V', 'GTG': 'V', 'GTT': 'V',
		'GCA': 'A', 'GCC': 'A', 'GCG': 'A', 'GCT': 'A',
		'GAC': 'D', 'GAT': 'D', 'GAA': 'E', 'GAG': 'E',
		'GGA': 'G', 'GGC': 'G', 'GGG': 'G', 'GGT': 'G',
		'TCA': 'S', 'TCC': 'S', 'TCG': 'S', 'TCT': 'S',
		'TTC': 'F', 'TTT': 'F', 'TTA': 'L', 'TTG': 'L',
		'TAC': 'Y', 'TAT': 'Y', 'TAA': '_', 'TAG': '_',
		'TGC': 'C', 'TGT': 'C', 'TGA': '_', 'TGG': 'W'}

		
		def check_codons(set_list):
			""" Given a list of sets, with the first element of a set containing the clade codons and the second
			element the other codons, this determines codon usage bias. For a given amino acid, it counts the usage of
			the codons for the clade and the other taxa """

			clade_count = {}
			other_count = {}

			for group in set_list:

				if group:
					for codon in group[0][0]:
						if codon_table[codon] in clade_count:
							clade_count[codon_table[codon]].append(codon)
						else:
							clade_count[codon_table[codon]] = [codon]

					for codon in group[0][1]:
						if codon_table[codon] in other_count:
							other_count[codon_table[codon]].append(codon)
						else:
							other_count[codon_table[codon]] = [codon]

			common_aa_list = [aa for aa in clade_count if aa in other_count]

			clade_storage = []
			other_storage = []

			for aa in common_aa_list:

				clade_temp_dic = {}
				other_temp_dic = {}

				clade_list = clade_count[aa]
				other_list = other_count[aa]

				total_list = clade_list + other_list

				for codon in set(total_list):

					clade_temp_dic[codon] = float(clade_list.count(codon)) / float(len(clade_list))
					other_temp_dic[codon] = float(other_list.count(codon)) / float(len(other_list))

				clade_storage.append((aa, clade_temp_dic))
				other_storage.append((aa, other_temp_dic))

			return other_storage, clade_storage

		def check_nucleotides(set_list):
			""" Given a list of sets, with the first element of a set containing the clade codons and the second
			element the other codons, it returns a list with two tuples [(clade nucleotide count (1,2,3,4)),
			(other nucleotide count (1,2,3,4)))] """

			nucleotides = ["A", "T", "G", "C"]
			clade_count = {"nucA": 0, "nucT": 0, "nucG": 0, "nucC": 0}
			other_count = {"nucA": 0, "nucT": 0, "nucG": 0, "nucC": 0}

			for group in set_list:
				for codon in group[0][0]:
					for nuc in nucleotides:
						clade_count["nuc%s" % nuc] += codon.count(nuc)

				# count nucleotides for other
				for codon in group[0][1]:
					for nuc in nucleotides:
						other_count["nuc%s" % nuc] += codon.count(nuc)

			# Get nucleotide proportions instead of absolute numbers
			clade_nuc_total = sum(clade_count.values())
			other_nuc_total = sum(other_count.values())

			clade_prop = dict((x, float(y) / float(clade_nuc_total)) for x, y in clade_count.items())
			other_prop = dict((x, float(y) / float(other_nuc_total)) for x, y in other_count.items())

			return clade_prop, other_prop

		def write_conserved(clade_storage, other_storage, file):
			""" Writes the frequency of used codons for conserved aminoacids to a csv"""
		
			for codon, clade_freq in clade_storage.items():
				other_freq = other_storage[codon]
				file.write(f"{codon};{clade_freq};{other_freq}\n")
    	
		conserved_storage = []
		mostly_conserved_storage = []
		all_conserved_storage = []
		all_mostly_conserved_storage = []

		for gene, pair in self.paml_pairs.items():

			if pair.conserved_aa is not None and pair.conserved_aa > 0 and pair.conserved_aa_list:
				conserved_storage.append(pair.conserved_aa_list)
		
			if pair.mostly_conserved is not None and pair.mostly_conserved > 0 and pair.mostly_conserved_aa_list:
				mostly_conserved_storage.append(pair.mostly_conserved_aa_list)
				
	
			all_conserved_storage.append(pair.all_conserved)
		

			all_mostly_conserved_storage.append(pair.all_mostly_conserved)


		conserved_counts_clade, conserved_counts_other = check_nucleotides(conserved_storage)
		mostly_conserved_counts_clade, mostly_conserved_counts_other = check_nucleotides(mostly_conserved_storage)	
 		
		# Write data to csv files
		with open(f"Conserved_nucleotide_trend.csv", "w") as f:
			f.write("nucleotide;clade_frequency;other_frequency\n")
			write_conserved(conserved_counts_clade, conserved_counts_other, f)
		
		with open(f"Mostly_Conserved_nucleotide_trend.csv", "w") as f:
			f.write("nucleotide;clade_frequency;other_frequency\n")	
			write_conserved(mostly_conserved_counts_clade, mostly_conserved_counts_other, f)	

		conserved_clade_codon, conserved_other_codon = check_codons(conserved_storage)
		mostly_conserved_clade_codon, mostly_conserved_other_codon = check_codons(mostly_conserved_storage)

		all_conserved_clade_codon, all_conserved_other_codon = check_codons(all_conserved_storage)
		all_mostly_conserved_clade_codon, all_mostly_conserved_other_codon = check_codons(all_mostly_conserved_storage)


		for clade, other in zip(conserved_clade_codon, conserved_other_codon):
			with open(f"Conserved_codon_trend{clade[0]}.csv", "w") as f:
				f.write("codon;clade_frequency;other_frequency\n")
				write_conserved(clade[1], other[1], f)
		
		for clade, other in zip(mostly_conserved_clade_codon, mostly_conserved_other_codon):
			with open(f"Mostly_Conserved_codon_trend{clade[0]}.csv", "w") as f:
				f.write("codon;clade_frequency;other_frequency\n")
				write_conserved(clade[1], other[1], f)

		for clade, other in zip(all_conserved_clade_codon, all_conserved_other_codon):		
			with open(f"All_Conserved_codon_trend{clade[0]}.csv", "w") as f:
				f.write("codon;clade_frequency;other_frequency\n")
				write_conserved(clade[1], other[1], f)
		
		for clade, other in zip(all_mostly_conserved_clade_codon, all_mostly_conserved_other_codon):		
			with open(f"All_Mostly_Conserved_codon_trend{clade[0]}.csv", "w") as f:
				f.write("codon;clade_frequency;other_frequency\n")
				write_conserved(clade[1], other[1], f)
    
    
	def write_table(self, output_file):
		""" Writes the information on the PamlPair objects into a csv table """

		output_handle = open(output_file, "w")
		output_handle.write("Gene;lnL Alternative;lnL Null;p-value;FDR correction;N sites;w class 0;w class 1;w class "
							"2;w class 3;Selected sites; Sites position; Conserved sites;Mostly conserved sites;Unique "
							"sites;Mostly unique;Diversifying sites;Mostly diverse; Shared; Variable; All unique sites\n")

		for gene, pair in self.paml_pairs.items():
			print("\rProcessing selection tests on file %s of %s (%s)" % (list(self.paml_pairs.values()).index(pair)+1,
																		len(self.paml_pairs.values()), pair.folder)),

			try:
				gene_length = pair.gene_length
			except:
				gene_length = None

			if pair.fdr_value < 0.05:
				output_handle.write("%s; %s; %s; %s; %s; %s; %s; %s;%s; %s; %s; %s; %s; %s; %s; %s; %s; %s; %s; %s; %s\n" % (
										gene,
										pair.alternative_lnL,
										pair.null_lnL,
										pair.pvalue,
										pair.fdr_value,
										gene_length,
										pair.conserved_prop,
										pair.neutral_prop,
										pair.high_selection_prop,
										pair.selection_prop,
										len(pair.selected_aa),
										pair.selected_aa,
										pair.conserved_aa,
										pair.mostly_conserved,
										pair.unique_aa,
										pair.mostly_unique,
										pair.diverse_aa,
										pair.mostly_diverse,
										pair.shared,
										pair.variable,
										pair.all_clade_unique))
			else:
				output_handle.write("%s; %s; %s; %s; %s; %s\n" % (gene,
																pair.alternative_lnL,
																pair.null_lnL,
																pair.pvalue,
																"",
																gene_length))

		output_handle.close()

if __name__ == "__main__":

	def main():
		# Arguments
		folder_list = arg.folder_list
		clade_list = arg.clade
		output_file = arg.output_file
		write_alignments = arg.write_alignments
		csv_options = arg.csv_options

		paml_output = PamlPairSet(folder_list)
		paml_output.test_selection_suite()

		if clade_list is not None:
			paml_output.filter_aa(clade_list, set_aa_columns=True)
		else:
			paml_output.filter_aa(clade_list)
		
		if write_alignments:

			paml_output.write_alignments()

		if csv_options is not None:
			paml_output.check_trend_conserve()

		#paml_output.get_class_proportion()
		paml_output.get_gene_class_proportions()
		paml_output.get_number_aa()
		paml_output.write_table(output_file)

	main()