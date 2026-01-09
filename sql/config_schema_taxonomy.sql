

--------------------------------------------------------------------------------------------
---module to set the schema taxonomy with two tables : taxa_refence, taxa_nameset
--set the constraints, sequences, function and triggers
--------------------------------------------------------------------------------------------


/*--delete all dependencies
	--drop trigger
	DROP TRIGGER IF EXISTS trigger_after_update ON taxonomy.taxa_reference CASCADE;
	DROP TRIGGER IF EXISTS trigger_before_update ON taxonomy.taxa_reference CASCADE;
	--drop view
	DROP VIEW IF EXISTS taxonomy.taxa_names CASCADE;
	--delete sequence 
	DROP SEQUENCE IF EXISTS taxonomy.taxa_id_taxonref_seq CASCADE;
	--delete constraints
	ALTER TABLE taxonomy.taxa_rank DROP CONSTRAINT IF EXISTS taxa_rank_un CASCADE;
	ALTER TABLE taxonomy.taxa_reference DROP CONSTRAINT IF EXISTS taxa_reference_pk CASCADE;
	ALTER TABLE taxonomy.taxa_reference DROP CONSTRAINT IF EXISTS taxa_reference_un CASCADE;
	ALTER TABLE taxonomy.taxa_reference DROP CONSTRAINT IF EXISTS id_parent_fk CASCADE;
	ALTER TABLE taxonomy.taxa_reference DROP CONSTRAINT IF EXISTS id_rank_fk CASCADE;
	ALTER TABLE taxonomy.taxa_reference DROP CONSTRAINT IF EXISTS check_name_length CASCADE;
	ALTER TABLE taxonomy.taxa_reference DROP CONSTRAINT IF EXISTS check_name_null_parent CASCADE;
	ALTER TABLE taxonomy.taxa_reference DROP CONSTRAINT IF EXISTS check_name_self_parent CASCADE;


	ALTER TABLE taxonomy.taxa_nameset DROP CONSTRAINT IF EXISTS taxa_name_fk CASCADE;
	ALTER TABLE taxonomy.taxa_nameset DROP CONSTRAINT IF EXISTS check_category CASCADE;
	ALTER TABLE taxonomy.taxa_nameset DROP CONSTRAINT IF EXISTS taxa_name_un CASCADE;
	ALTER TABLE taxonomy.taxa_nameset DROP COLUMN IF EXISTS _keyname;


---delete functions
	DROP FUNCTION IF EXISTS taxonomy.pn_names_add(INTEGER,TEXT,TEXT) CASCADE;
	DROP FUNCTION IF EXISTS taxonomy.pn_names_delete (TEXT) CASCADE;
	DROP FUNCTION IF EXISTS taxonomy.pn_names_items(INTEGER) CASCADE;
	DROP FUNCTION IF EXISTS taxonomy.pn_names_update(TEXT,TEXT,TEXT) CASCADE;

	DROP FUNCTION IF EXISTS taxonomy.pn_ranks_children(INTEGER) CASCADE;
	DROP FUNCTION IF EXISTS taxonomy.pn_ranks_name(INTEGER) CASCADE;
	DROP FUNCTION IF EXISTS taxonomy.pn_ranks_parents(INTEGER) CASCADE;	
	DROP FUNCTION IF EXISTS taxonomy.pn_taxa_authors_score(int4);
	
	DROP FUNCTION IF EXISTS taxonomy.pn_taxa_childs(INTEGER, BOOLEAN, BOOLEAN) CASCADE;
	DROP FUNCTION IF EXISTS taxonomy.pn_taxa_delete (INTEGER, BOOLEAN) CASCADE;
	DROP FUNCTION IF EXISTS taxonomy.pn_taxa_edit (INTEGER, TEXT, TEXT, INTEGER, INTEGER, BOOLEAN, BOOLEAN) CASCADE;
	DROP FUNCTION IF EXISTS taxonomy.pn_taxa_getparent(INTEGER, INTEGER) CASCADE;
	DROP FUNCTION IF EXISTS taxonomy.pn_taxa_keyname(TEXT) CASCADE;
	DROP FUNCTION IF EXISTS taxonomy.pn_taxa_parents(INTEGER, BOOLEAN) CASCADE;	
	DROP FUNCTION IF EXISTS taxonomy.pn_taxa_refresh_nameset(INTEGER);
	DROP FUNCTION IF EXISTS taxonomy.pn_taxa_searchname (TEXT, NUMERIC) CASCADE;
	DROP FUNCTION IF EXISTS taxonomy.pn_taxa_searchnames (text[]) CASCADE;
	DROP FUNCTION IF EXISTS taxonomy.pn_taxa_searchtable (TEXT, TEXT) CASCADE;	
	DROP PROCEDURE IF EXISTS taxonomy.pn_taxa_set_synonymy(INTEGER, INTEGER, TEXT);
	
	DROP FUNCTION IF EXISTS taxonomy.pn_trigger_check_reference() CASCADE;
	DROP FUNCTION IF EXISTS taxonomy.pn_trigger_refresh_nameset() CASCADE;

	--DROP FUNCTION IF EXISTS taxonomy.pn_taxa_synonyms(INTEGER) CASCADE;
	--DROP FUNCTION IF EXISTS taxonomy.pn_taxa_merge(int4, int4, text, bool) CASCADE;
	--DROP FUNCTION IF EXISTS taxonomy.pn_taxa_move(int4, int4, text, bool) CASCADE;

	
	
	
--add constraints
	--on taxa_rank
	ALTER TABLE taxonomy.taxa_rank ADD CONSTRAINT taxa_rank_un UNIQUE (id_rank);
	ALTER TABLE taxonomy.taxa_rank ALTER COLUMN id_rank  SET NOT NULL;
	ALTER TABLE taxonomy.taxa_rank ALTER COLUMN rank_name  SET NOT NULL;
	--on taxa_reference
	ALTER TABLE taxonomy.taxa_reference ALTER COLUMN id_taxonref  SET NOT NULL;
	ALTER TABLE taxonomy.taxa_reference ALTER COLUMN basename SET NOT NULL;
	ALTER TABLE taxonomy.taxa_reference ALTER COLUMN id_rank SET NOT NULL;

	ALTER TABLE taxonomy.taxa_reference ALTER COLUMN accepted SET DEFAULT TRUE;
	ALTER TABLE taxonomy.taxa_reference ADD CONSTRAINT taxa_reference_pk PRIMARY KEY (id_taxonref);
	ALTER TABLE taxonomy.taxa_reference ADD CONSTRAINT taxa_reference_un UNIQUE (basename, id_parent);
	ALTER TABLE taxonomy.taxa_reference ADD CONSTRAINT id_parent_fk FOREIGN KEY (id_parent) REFERENCES taxonomy.taxa_reference(id_taxonref) ON UPDATE CASCADE ON DELETE CASCADE;
	ALTER TABLE taxonomy.taxa_reference ADD CONSTRAINT id_rank_fk FOREIGN KEY (id_rank) REFERENCES taxonomy.taxa_rank(id_rank);
	ALTER TABLE taxonomy.taxa_reference ADD CONSTRAINT check_name_length CHECK (id_rank <14 OR length(basename) >= 3);
	
	ALTER TABLE taxonomy.taxa_reference ADD CONSTRAINT check_name_null_parent CHECK (id_rank =1 OR id_parent IS NOT NULL);
	ALTER TABLE taxonomy.taxa_reference ADD CONSTRAINT check_name_self_parent CHECK (id_parent IS NULL OR id_parent <> id_taxonref);	

	--on taxa_nameset
	ALTER TABLE taxonomy.taxa_nameset ALTER COLUMN name SET NOT NULL;
	ALTER TABLE taxonomy.taxa_nameset ALTER COLUMN category SET DEFAULT 5;
	ALTER TABLE taxonomy.taxa_nameset ADD CONSTRAINT check_category CHECK (category BETWEEN 0 AND 9);
	ALTER TABLE taxonomy.taxa_nameset ADD CONSTRAINT taxa_name_fk FOREIGN KEY (id_taxonref) REFERENCES taxonomy.taxa_reference(id_taxonref) ON UPDATE CASCADE ON DELETE CASCADE;
--add sequence
	CREATE SEQUENCE taxonomy.taxa_id_taxonref_seq OWNED BY taxonomy.taxa_reference.id_taxonref;
	SELECT SETVAL('taxonomy.taxa_id_taxonref_seq', COALESCE(MAX(id_taxonref), 0) + 1, false) FROM taxonomy.taxa_reference;
	ALTER TABLE taxonomy.taxa_reference ALTER COLUMN id_taxonref SET DEFAULT NEXTVAL('taxonomy.taxa_id_taxonref_seq');

	*/




-------------------------------------------------------------
--------------CREATE taxonomic Functions
-------------------------------------------------------------

---------------------------------------------------------------------------------------------------------------
-------##Function to clean a taxa name by deleting special terms (sp., sp.nov., spp., cf. aff., af.)
-------and to encode the name for similarity search name+metaphone+soundex 
---------------------------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION taxonomy.pn_taxa_keyname (
	taxa_name	TEXT
	)
RETURNS TEXT
LANGUAGE plpgsql
IMMUTABLE
AS $function$

/* check for validity
--test for the duplicate keynames
	SELECT * FROM
	(SELECT array_agg(original_name), key_name, count(key_name) count, array_agg(type_name), array_agg(DISTINCT id_taxonref)
	FROM taxonomy.pn_names_items()
	GROUP BY key_name) z 
	WHERE z.count >1
--test for special names
	select taxonomy.pn_taxa_keyname ('Miconia calvescens DC')
	select taxonomy.pn_taxa_keyname ('Miconia calvescens var. trinerva')
	select taxonomy.pn_taxa_keyname ('Alstonia coriacea Pancher ex S. Moore') = taxonomy.pn_taxa_keyname ('Alstonia coriacea Pancher ex S.Moore')

	select taxonomy.pn_taxa_keyname ('Miconia calvescens Birnbaum ex DC. ssp. bidule DC. ex. Guillaumin')
	select * from taxonomy.pn_taxa_searchname('Alstonia coriacea Pancher ex S. Moore', 0.8)
 * */
DECLARE
	text_search TEXT;
	stop_words	TEXT;

BEGIN
--normalize names with regex
	--consider f. as forma if follow by at least three lowercase characters
	text_search = regexp_replace(taxa_name, 'f\. ([a-z]{3,})', 'forma \1', 'g');
	--switch to lower case
	text_search = lower(taxa_name) ||  ' ';
	-- exclude text in bracket [ ]
	text_search = regexp_replace (text_search,'\[.*?\]',' ', 'g');
	--delete non-alpha numeric character
	text_search = regexp_replace (text_search,'[^a-z0-9\säëïüàâçèéêîôùû]','', 'g');
	--stop_words list of deleted word (useless terms)
	stop_words = 'spp|spnov|sp|nov|ined|nom|illeg|nomilleg|cf|aff|af|comb|combined';
	text_search = regexp_replace(text_search, '\m(' || stop_words || ')\M',' ', 'g');
	--normalize some infraspecific variants prefix
	text_search = replace(text_search, ' ssp ',' subsp ');
    --text_search = replace(text_search, ' forma ',' f ');
	--delete infraspecific prexif located at the end of the text
	stop_words = 'var|forma|subsp|subg';
	text_search = regexp_replace(text_search, '\m(' || stop_words || ')\M\s*$','', 'g');

	--replace all multi-space by only one
	--text_search = regexp_replace(text_search, '\s+',' ', 'g');
	text_search = regexp_replace(text_search, '\s','', 'g');

--text_search = concat_ws('-', trim(text_search), metaphone(text_search,8));
RETURN trim(text_search);
END
$function$;
COMMENT ON FUNCTION taxonomy.pn_taxa_keyname(TEXT) IS 'Return the input taxa_name as a code in lower case';


-----------------------------------------------------------------------------------------------------
--add a autogenerated column to taxa_nameset based on the function taxonomy.pn_taxa_keyname
-----------------------------------------------------------------------------------------------------
ALTER TABLE taxonomy.taxa_nameset ADD COLUMN _keyname TEXT GENERATED ALWAYS AS (taxonomy.pn_taxa_keyname(name)) STORED;
COMMENT ON COLUMN taxonomy.taxa_nameset._keyname IS 'the normalized name of the synonym (only alphanumeric character)';
ALTER TABLE taxonomy.taxa_nameset ADD CONSTRAINT taxa_name_un UNIQUE (_keyname);

-----------------------------------------------------------------------------------------------
--create a view by crossing the table taxonomy.taxa_reference with keynames2
------------------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW taxonomy.taxa_names AS
	SELECT 
		a.id_taxonref, a.id_rank,  a.id_parent, 
		a.basename, a.authors,
		COALESCE (c.name,b.name) AS taxaname, 
		b.name AS taxonref,
		a.published,
		a.accepted,
		a.metadata, a.properties
	FROM taxonomy.taxa_reference a
	INNER JOIN taxonomy.taxa_nameset b ON a.id_taxonref = b.id_taxonref AND b.category = 1 
	LEFT JOIN taxonomy.taxa_nameset c ON a.id_taxonref = c.id_taxonref AND c.category = 2;
COMMENT ON VIEW taxonomy.taxa_names IS 'View to display accepted name with taxa_reference columns'
;


---------------------------------------------------------------------------------------------------------------
-------##search the corresponding name from a text with a similarity threshold (1 IS default)
-----------------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION taxonomy.pn_taxa_searchname (
	search_name	TEXT,
	similarity NUMERIC DEFAULT 1
	)
RETURNS TABLE(
	id_taxonref		INTEGER, 
	taxonref		TEXT,
	score			INTEGER
	)
LANGUAGE plpgsql
STABLE
AS $function$
/*
	SELECT * FROM taxonomy.pn_taxa_searchname('*anthus*')
	SELECT * FROM taxonomy.pn_taxa_searchname('Osmanthus')
	SELECT * FROM taxonomy.pn_taxa_searchname('Zygogynum',0.6)
	SELECT * FROM taxonomy.taxa_nameset where id_taxonref = 6314
 */
DECLARE
	_search_keyname	TEXT;

BEGIN
	SELECT least(greatest(similarity, 0), 1) INTO similarity;
	SELECT taxonomy.pn_taxa_keyname(search_name) INTO _search_keyname;
	search_name = REPLACE(search_name,'*','%');


	IF search_name LIKE '%\%%' THEN
		RETURN query
			SELECT DISTINCT b.id_taxonref ::INTEGER, b.name::TEXT taxonref , 100 ::INTEGER score
			FROM taxonomy.taxa_nameset a
			INNER JOIN taxonomy.taxa_nameset b ON a.id_taxonref = b.id_taxonref				
			WHERE a.name ILIKE search_name
			AND b.category = 1
			ORDER BY b.name;
	ELSE --SEARCH FOR fuzzymatch and return value according to similarity
		RETURN query
			--pre-select taxa according to a levenshtein distance between short metaphone codes
			WITH keynames AS 
				(SELECT w.id_taxonref, _keyname AS key_name 
				 FROM taxonomy.taxa_nameset w
				 WHERE levenshtein(metaphone(w.name, 5), metaphone(search_name, 5)) <2
				)
			SELECT DISTINCT a.id_taxonref ::INTEGER, a.taxonref ::TEXT,  round(100*max(a.score)) ::INTEGER score
			FROM 
				(SELECT b.id_taxonref, b.name as taxonref, a.score 
				 FROM
					(SELECT 
						z.id_taxonref,
						(2 * similarity(_search_keyname, z.key_name) 
						 +   similarity(dmetaphone(_search_keyname), dmetaphone(z.key_name))
						) / 3
						AS score
					 FROM keynames z) a
				 INNER JOIN taxonomy.taxa_nameset b ON a.id_taxonref = b.id_taxonref 
				 WHERE a.score >= similarity and b.category = 1
				) a	
			GROUP BY a.id_taxonref, a.taxonref
			ORDER BY score DESC, a.taxonref;
	END IF;
END;
$function$;
COMMENT ON FUNCTION taxonomy.pn_taxa_searchname (TEXT, NUMERIC) IS 'Search for a taxon name. Returns table with id_taxonref, taxonref and the search score'
;




---------------------------------------------------------------------------------------------------------------
-------##return a table with valid names from an array of taxa_names
---------------------------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION taxonomy.pn_taxa_searchnames (
	names_array text[]
	)
RETURNS TABLE(
	id_taxonref		INTEGER,
	taxonref		TEXT,
	original_name	TEXT 
	)
LANGUAGE plpgsql
STABLE
AS $function$
/*
dependencies :
- taxonomy.taxa_nameset

	from a list of values
		SELECT * FROM taxonomy.pn_taxa_searchnames( array['houp', 'Dysoxylum','bidule'])  WHERE id_taxonref IS NOT NULL
	from a query
		SELECT * FROM taxonomy.pn_taxa_searchnames (array(select taxaname::TEXT from occurrences.occ_ncpippn))
		WHERE id_taxonref IS  NULL
*/
BEGIN
	RETURN QUERY
		SELECT c.id_taxonref, c.name AS taxonref, a.name 
		FROM (SELECT name FROM UNNEST (names_array) AS t(name) GROUP BY name) a 
		
		LEFT JOIN taxonomy.taxa_nameset b 
		ON taxonomy.pn_taxa_keyname(a.name) = taxonomy.pn_taxa_keyname(b.name)
		
		LEFT JOIN taxonomy.taxa_nameset c 
		ON b.id_taxonref = c.id_taxonref AND c.category = 1

		WHERE a.name IS NOT NULL;
END
$function$;
COMMENT ON FUNCTION taxonomy.pn_taxa_searchnames (text[]) IS 'Search for taxa names from a text array. Returns a table with the id_taxonref, taxonref matching with the original_name'
;


---------------------------------------------------------------------------------------------------------------
-------return a table of translated valid names from a schema.table and a fieldname containing taxa_names
---------------------------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION taxonomy.pn_taxa_searchtable (
	schema_table	TEXT, 
	field_name		TEXT
	)
RETURNS TABLE(
 	id_taxonref		INTEGER,
 	taxonref		TEXT,
	original_name	TEXT 
	)
LANGUAGE plpgsql
AS $function$ 
/*
 * dependencies function taxonomy.pn_taxa_searchnames
 */
---SELECT * FROM taxonomy.pn_taxa_searchtable ('occurrences.occ_ncpippn', 'taxaname')
BEGIN
RETURN QUERY 
EXECUTE
	Format ('SELECT * FROM taxonomy.pn_taxa_searchnames (array(SELECT %s::TEXT FROM %s)) b',
			 field_name,schema_table
	);
	END
$function$;
COMMENT ON FUNCTION taxonomy.pn_taxa_searchtable (TEXT, TEXT) IS 'Search for taxa names included within a table. Returns a table with the id_taxonref, taxonref, original_name matching with the field_name'
;


-----------------------------------------------------------------------------------------------
---Add (id_synomy = 0) or Update (id_synonym >0)
---RETURN id_synonym if the execution of the SQL statement (update or insert) is successfull
------------------------------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION taxonomy.pn_names_add (
	idtaxonref 	INTEGER,
	nametoadd 	TEXT,
	tocategory 	TEXT DEFAULT 'orthographic'
	) 
	
RETURNS TEXT 
LANGUAGE plpgsql AS $function$
/*
To add a new Synonym with a id_taxonref = 4335
	SELECT taxonomy.pn_names_add ('Essai de nom','Orthographic',4335)
	
*/
DECLARE
	newitem TEXT;
	newcategory	INTEGER;
BEGIN
	tocategory = lower(tocategory);
	SELECT 
		CASE 
			WHEN tocategory = 'nomenclatural' THEN 5
			WHEN tocategory = 'taxinomic' THEN 6
			WHEN tocategory = 'common' THEN 7
			WHEN tocategory = 'orthographic' THEN 8
		ELSE 9
		END
	INTO newcategory;
		

	-- Raise errors if id_taxonref equal to zero (integrity with existing id_taxonref)
		INSERT INTO taxonomy.taxa_nameset (name, category, id_taxonref)
		VALUES (nametoadd, newcategory, idtaxonref) 
		RETURNING name INTO newitem;
	RETURN newitem;
END;
$function$;
COMMENT ON FUNCTION taxonomy.pn_names_add(INTEGER,TEXT,TEXT) IS 'Add a name to the global nameset'
;

-----------------------------------------------------------------------------------------------
---update a name in the nameDataSet
---RETURN the new name if success
------------------------------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION taxonomy.pn_names_update (
	nametoupdate 		TEXT,
	newname				TEXT,
	newcategory 		TEXT DEFAULT NULL
	)
	
RETURNS TEXT 
LANGUAGE plpgsql AS $function$
/*
To update a new Synonym with a id_taxonref = 4335
	SELECT taxonomy.pn_names_update ('Essai de nom', 'Essai de nom2')
SELECT taxonomy.pn_names_update ('testouillette','testouillettes', 'Orthographic')
	
*/
DECLARE
	_updateitem TEXT;
	_category	INTEGER;
BEGIN
	IF newcategory IS NOT NULL THEN
		newcategory = lower(newcategory);
		SELECT 
			CASE 
				WHEN newcategory = 'nomenclatural' THEN 5
				WHEN newcategory = 'taxinomic' THEN 6
				WHEN newcategory = 'common' THEN 7
				WHEN newcategory = 'orthographic' THEN 8
			ELSE 9
			END
		INTO _category;
	ELSE
		SELECT category INTO _category FROM taxonomy.taxa_nameset WHERE name = nametoupdate;
	END IF;

	UPDATE taxonomy.taxa_nameset
	SET name = newname,
		category = _category
	WHERE name = nametoupdate
	RETURNING newname INTO _updateitem;

	RETURN _updateitem;
END;
$function$;

COMMENT ON FUNCTION taxonomy.pn_names_update(TEXT,TEXT,TEXT) IS 'update the name (and category if present) into the global NameDataSet'
;


---------------------------------------------------------------------------------------------------------------
-------delete a synonym name, return TRUE if success OR FALSE if idsynonym is not found
---------------------------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION taxonomy.pn_names_delete (
	nametodelete		text
	)
RETURNS BOOLEAN
LANGUAGE plpgsql AS 
$function$
/*
	SELECT taxonomy.pn_names_delete ('Essai de nom2')
 */
DECLARE
	_isdeleted	BOOLEAN;

BEGIN
		DELETE 
		FROM taxonomy.taxa_nameset w
		WHERE w.name = nametodelete and category >= 5
		RETURNING nametodelete IS NOT NULL INTO _isdeleted;

RETURN _isdeleted;
	END;
$function$;
COMMENT ON FUNCTION taxonomy.pn_names_delete (TEXT) IS 'Delete a name, return True/False';


-----------------------------------------------------------------------------------------------
---Returns all synonyms names from a id_taxonref
------------------------------------------------------------------------------------------------

--DROP FUNCTION taxonomy.pn_names_items(integer); 
CREATE OR REPLACE FUNCTION taxonomy.pn_names_items (
	idtaxonref INTEGER
	) 
RETURNS TABLE(
	name		TEXT,
	category	TEXT,
	id_category	INTEGER
	) 
LANGUAGE plpgsql STABLE AS
$function$
/*
 	SELECT * FROM  taxonomy.pn_names_items(15570)
 */
BEGIN
	RETURN QUERY
	SELECT 
		a.name,  
			CASE 
				WHEN a.category = 1 THEN 'Taxonref'
				WHEN a.category = 2 THEN 'Taxaname'
				WHEN a.category = 3 THEN 'Alternative'
				WHEN a.category = 4 THEN 'Autonym'
				WHEN a.category = 5 THEN 'Nomenclatural'
				WHEN a.category = 6 THEN 'Taxinomic'
				WHEN a.category = 7 THEN 'Common'
				WHEN a.category = 8 THEN 'Orthographic'
			ELSE 'Unknown'
			END
			AS _category,
			a.category
	FROM taxonomy.taxa_nameset a
	WHERE a.id_taxonref = idtaxonref
	ORDER BY a.category, a.name;
END;
$function$;
COMMENT ON FUNCTION taxonomy.pn_names_items(INTEGER) IS 'Return a table containing names of the input idtaxonref';	





-----------------------------------------------------------------------------------------------
---#Return a text corresponding to the input id_rank
------------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION taxonomy.pn_ranks_name (
	idrank	INTEGER
	) 
RETURNS TEXT 
LANGUAGE plpgsql STABLE AS
$function$
/* example
 SELECT * FROM  taxonomy.pn_ranks_name(21)
 */
DECLARE
	ranktext	text;
BEGIN
	SELECT rank_name INTO ranktext FROM taxonomy.taxa_rank WHERE id_rank = idrank;	
	RETURN ranktext;
END;
$function$;
COMMENT ON FUNCTION taxonomy.pn_ranks_name(INTEGER) IS 'Return the rank name from the input id_rank';	




-----------------------------------------------------------------------------------------------
---#Return a table with the authorised childs ranks for a input id_rank
------------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION taxonomy.pn_ranks_children (
	idrank	INTEGER
	) 
RETURNS TABLE(
	id_rank	INTEGER
	)
LANGUAGE plpgsql STABLE AS
$function$

/* example
	select * from taxonomy.pn_ranks_children(14)
	select id_rank, taxonomy.pn_ranks_name(id_rank) from taxonomy.pn_ranks_children(14)
 */

BEGIN
	RETURN QUERY
		SELECT a.id_rank from taxonomy.taxa_rank a
		WHERE a.id_rankparent <= idrank AND a.id_rank > idrank
		ORDER BY a.id_rank;
END;
$function$;
COMMENT ON FUNCTION taxonomy.pn_ranks_children(INTEGER) IS 'Return the authorized childs ranks for the input id_rank';	


--CREATE OR REPLACE FUNCTION taxonomy.pn_ranks_children (
--	idrank	INTEGER
--	) 
--RETURNS TABLE(
--	id_rank	INTEGER
--	)
--LANGUAGE plpgsql STABLE AS
--$function$
--/* example
--	select * from taxonomy.pn_ranks_children(14)
--	select id_rank, taxonomy.pn_ranks_name(id_rank) from taxonomy.pn_ranks_children(14)
-- */
--
--BEGIN
--	RETURN QUERY
--SELECT ranks.id_rank
--FROM
--	(
--	SELECT
--	UNNEST (
--	CASE  
--		WHEN a.id_rank =1  THEN ARRAY[2, 3] --
--		WHEN a.id_rank =2  THEN ARRAY[3]
--		WHEN a.id_rank =3  THEN ARRAY[4, 5, 6] --
--		WHEN a.id_rank =4  THEN ARRAY[5,6]
--		WHEN a.id_rank =5  THEN ARRAY[6]
--		WHEN a.id_rank =6  THEN ARRAY[7, 8]
--		WHEN a.id_rank =7  THEN ARRAY[8]
--		WHEN a.id_rank =8  THEN ARRAY[9, 10]
--		WHEN a.id_rank =9  THEN ARRAY[10]
--		WHEN a.id_rank =10 THEN ARRAY[11, 12, 14]
--		WHEN a.id_rank =11 THEN ARRAY[12, 14] 
--		WHEN a.id_rank =12 THEN ARRAY[13, 14]
--		WHEN a.id_rank =13 THEN ARRAY[14]
--		WHEN a.id_rank =14 THEN ARRAY[15, 16, 18, 21, 31]
--		WHEN a.id_rank =15 THEN ARRAY[16, 18, 21, 31]
--		WHEN a.id_rank =16 THEN ARRAY[17, 18, 21, 31]
--		WHEN a.id_rank =17 THEN ARRAY[18, 21, 31]
--		WHEN a.id_rank =18 THEN ARRAY[19, 21, 31]
--		WHEN a.id_rank =19 THEN ARRAY[21, 31] 
--		WHEN a.id_rank =21 THEN ARRAY[22, 23, 25, 27, 28, 31] --
--		WHEN a.id_rank =22 THEN ARRAY[23, 25, 27, 28, 31] 
--		WHEN a.id_rank =23 THEN ARRAY[24, 25, 27, 28, 31] --
--	WHEN a.id_rank =24 THEN ARRAY[25, 28, 31] -- +27
--	WHEN a.id_rank =25 THEN ARRAY[26, 27, 31] -- +28
--		ELSE  NULL
--	END) id_rank
--		FROM taxonomy.taxa_rank a WHERE a.id_rank = idrank
--	) ranks
--	ORDER BY ranks.id_rank;	
--END;
--$function$;
--COMMENT ON FUNCTION taxonomy.pn_ranks_children(INTEGER) IS 'Return the authorized childs ranks for the input id_rank';	
--
--
--
--
--CREATE OR REPLACE FUNCTION taxonomy.pn_ranks_parents (
--	idrank	INTEGER
--	) 
--RETURNS TABLE(
--	id_rank	INTEGER
--	)
--LANGUAGE plpgsql STABLE AS
--$function$
--/* example
--	select * from taxonomy.pn_ranks_parents(21)
--	select id_rank, taxonomy.pn_ranks_name(id_rank) from taxonomy.pn_ranks_parents(21)
-- */
--
--BEGIN
--	RETURN QUERY
--SELECT ranks.id_rank
--FROM
--	(
--	SELECT
--	UNNEST (
--	CASE  
--		WHEN a.id_rank =2  THEN ARRAY[1] --
--		WHEN a.id_rank =3  THEN ARRAY[1, 2] 
--		WHEN a.id_rank =4  THEN ARRAY[3]
--		WHEN a.id_rank =5  THEN ARRAY[3, 4]
--		WHEN a.id_rank =6  THEN ARRAY[3, 4, 5]
--		WHEN a.id_rank =7  THEN ARRAY[6]
--		WHEN a.id_rank =8  THEN ARRAY[6, 7]
--		WHEN a.id_rank =9  THEN ARRAY[8]
--		WHEN a.id_rank =10 THEN ARRAY[8, 9]
--		WHEN a.id_rank =11 THEN ARRAY[10] 
--		WHEN a.id_rank =12 THEN ARRAY[11, 10]
--		WHEN a.id_rank =13 THEN ARRAY[12]
--		WHEN a.id_rank =14 THEN ARRAY[10, 11, 12, 13]
--		WHEN a.id_rank =15 THEN ARRAY[14]
--		WHEN a.id_rank =16 THEN ARRAY[14, 15]
--		WHEN a.id_rank =17 THEN ARRAY[16]
--		WHEN a.id_rank =18 THEN ARRAY[14, 15, 16, 17]
--		WHEN a.id_rank =19 THEN ARRAY[18] 
--		WHEN a.id_rank =21 THEN ARRAY[14, 15, 16, 17, 18, 19] --
--		WHEN a.id_rank =22 THEN ARRAY[21] 
--		WHEN a.id_rank =23 THEN ARRAY[21, 22] --
--		WHEN a.id_rank =24 THEN ARRAY[23] --
--		WHEN a.id_rank =25 THEN ARRAY[21, 22, 23, 24]
--		WHEN a.id_rank =26 THEN ARRAY[25]
--		WHEN a.id_rank =27 THEN ARRAY[21, 22, 23, 25]
--		WHEN a.id_rank =28 THEN ARRAY[21, 22, 23, 24]
--		WHEN a.id_rank =31 THEN ARRAY[14, 15, 16, 17, 18, 19, 21, 22, 23, 25, 26]
--
--
--		ELSE  NULL
--	END) id_rank
--		FROM taxonomy.taxa_rank a WHERE a.id_rank = idrank
--	) ranks
--	ORDER BY ranks.id_rank;	
--END;
--$function$;
--COMMENT ON FUNCTION taxonomy.pn_ranks_parents(INTEGER) IS 'Return the authorized parents ranks for the input id_rank';	
--




-----------------------------------------------------------------------------------------------
---#Return the parent according to the idrank
------------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION taxonomy.pn_taxa_getparent(
	idtaxonref	INTEGER,
	idrank		INTEGER
	)
RETURNS INTEGER  LANGUAGE plpgsql
STABLE
AS $function$
/*
 	SELECT * from taxonomy.pn_taxa_getparent(1575,10)  --return the family of the id_taxonref = 1575
 	SELECT * from taxonomy.pn_taxa_getparent(1575,14)  --return the genus of the id_taxonref = 1575
 	SELECT * from taxonomy.pn_taxa_getparent(14934,14) --return the species from a genus-hybrid == NULL

*/
DECLARE 
	_idrank INTEGER;
	_idtaxonref INTEGER;

BEGIN
	IF idtaxonref IS NULL THEN
		RETURN NULL;
	END IF;

	SELECT a.id_rank INTO _idrank FROM taxonomy.taxa_reference a WHERE a.id_taxonref = idtaxonref;
	_idtaxonref = idtaxonref;
	--loop on the parent until to find the idrank
	WHILE _idrank > idrank
	LOOP
		SELECT a.id_parent INTO _idtaxonref FROM taxonomy.taxa_reference a WHERE a.id_taxonref = idtaxonref;
		SELECT a.id_rank INTO _idrank FROM taxonomy.taxa_reference a WHERE a.id_taxonref = _idtaxonref;
		idtaxonref = _idtaxonref;
	END LOOP;
	--return NULL if result is not the expecting idrank
	IF _idrank <> idrank THEN 
		_idtaxonref = NULL; 
	END IF;

	RETURN _idtaxonref;
END;
$function$;
COMMENT ON FUNCTION taxonomy.pn_taxa_getparent(INTEGER, INTEGER) IS 'Return an integer corresponding to the id_parent at the specified id_rank';	








-----------------------------------------------------------------------------------------------
---Add (idtaxonref = 0) or update (idtaxonref >0) a taxa into the reference table
------------------------------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION taxonomy.pn_taxa_edit (
	idtaxonref 		INTEGER,
	newbasename		TEXT,
	newauthors		TEXT DEFAULT NULL,
	newidparent		INTEGER DEFAULT NULL,
	newidrank		INTEGER DEFAULT NULL,
	newpublished	BOOLEAN DEFAULT TRUE,
	newaccepted		BOOLEAN DEFAULT TRUE
	)
RETURNS INTEGER  
LANGUAGE plpgsql
AS $function$

DECLARE
	_isnewtaxa		BOOLEAN;
	_idtaxonref		INTEGER;	

/*
 * if idtaxonref <=0 -->> Add new taxa, others parameters must be set
SELECT * FROM taxonomy.pn_taxa_edit (0, 'abelmoschus', 'Birnbaum', 1040, 21, False, False)
select * from taxonomy.pn_taxa_childs (16881, TRUE)
SELECT * FROM taxonomy.pn_taxa_edit (1040, 'Birnbaum', 'Birnbaum', 16217, 10, False, False)

**/

BEGIN

	_isnewtaxa = (idtaxonref <= 0);
---------------------
--Tests for the validity of request and raise errors


--check newidparent if NULL (in case of idtaxonref <=0, i.e. _isnewtaxa = True then the result is NULL)
	IF newidparent IS NULL THEN
		SELECT a.id_parent INTO newidparent FROM taxonomy.taxa_reference a WHERE a.id_taxonref = idtaxonref;
	END IF;	
	IF newidrank IS NULL THEN
		SELECT a.id_rank INTO newidrank FROM taxonomy.taxa_reference a WHERE a.id_taxonref = idtaxonref;
	END IF;
--if one of the three parameters is NULL then Errors in the database structure 
	IF newidparent IS NULL OR newidrank IS NULL OR LENGTH(newbasename) = 0 THEN
		RAISE check_violation USING DETAIL = 'Editing is failed : basename, idparent or idrank are invalid parameters' ;
	END IF;

--execute query
	IF _isnewtaxa THEN
		--insert the new taxon
		INSERT INTO taxonomy.taxa_reference AS a (basename, id_rank, id_parent, authors, published, accepted)
		VALUES (newbasename, newidrank, newidparent, newauthors, newpublished, newaccepted)
		RETURNING a.id_taxonref INTO _idtaxonref;
	ELSE --update values
		UPDATE taxonomy.taxa_reference a
			SET basename = newbasename,
				id_parent = newidparent,
				id_rank = newidrank,
				authors = newauthors,
				published = newpublished,
				accepted = newaccepted
			WHERE a.id_taxonref = idtaxonref
		RETURNING a.id_taxonref INTO _idtaxonref;
	END IF;

RETURN _idtaxonref;

	--SELECT * FROM taxonomy.pn_taxa_childs (idtaxonref, TRUE, FALSE);

END;
$function$;
COMMENT ON FUNCTION taxonomy.pn_taxa_edit (INTEGER, TEXT, TEXT, INTEGER, INTEGER, BOOLEAN, BOOLEAN) IS 'Edit the taxa reference (add id idtaxonref = 0), change properties, update childs taxanames and synonyms';





-----------------------------------------------------------------------------------------------
---Delete a taxa (+ childs + synonyms)
------------------------------------------------------------------------------------------------
--DROP FUNCTION taxonomy.pn_taxa_delete
CREATE OR REPLACE FUNCTION taxonomy.pn_taxa_delete (
	idtaxonref 		INTEGER
	)
RETURNS INTEGER  
LANGUAGE plpgsql
AS $function$
/*
	SELECT taxonomy.pn_taxa_delete (12449)
*/
DECLARE
	_idtaxonref		INTEGER;
	_idparent		INTEGER;
	_idrank			INTEGER;

BEGIN
	--delete in cascade
		DELETE 
		FROM taxonomy.taxa_reference a 
		WHERE a.id_taxonref = idtaxonref
		RETURNING id_taxonref, id_parent, id_rank INTO _idtaxonref, _idparent, _idrank;

	-- if rank is below species rank (id_rank > 21)
	-- simulate change to fire the trigger on species names into taxa_nameset (cf. pn_trigger_refresh_nameset)
		IF _idrank > 21 THEN
			UPDATE taxonomy.taxa_reference a
			SET id_taxonref = id_taxonref
			WHERE id_taxonref = taxonomy.pn_taxa_getparent (_idparent, 21);
		END IF;
--returns the result of the query
	RETURN 
		_idtaxonref AS id_taxonref;
END;
$function$;
COMMENT ON FUNCTION taxonomy.pn_taxa_delete (INTEGER) IS 'Delete a taxa including childs and synonyms';





-----------------------------------------------------------------------------------------------
---#Return a table of the id_taxonref childs (and input idtaxonref if included is TRUE)
---If linked_ranks is set to True, return only id_taxonref whose taxaname includes the basename of idtaxonref among its parts.
------------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION taxonomy.pn_taxa_childs(
    idtaxonref   integer,
    included     boolean DEFAULT false,
    linked_ranks boolean DEFAULT false
)
RETURNS TABLE(id_taxonref integer)
LANGUAGE sql
STABLE
AS $$
WITH RECURSIVE params AS (
    SELECT
        CASE
            WHEN linked_ranks = FALSE THEN 1000
            WHEN w.id_rank IN (6, 8, 10, 12) THEN w.id_rank + 1
            WHEN w.id_rank >= 14 THEN 1000
            ELSE w.id_rank
        END AS idrank_max
    FROM taxonomy.taxa_reference w
    WHERE w.id_taxonref = idtaxonref
),
taxa_tree AS (
    -- anchor
    SELECT t1.id_taxonref
    FROM taxonomy.taxa_reference t1
    CROSS JOIN params p
    WHERE t1.id_rank <= p.idrank_max
      AND (
        CASE WHEN included
             THEN t1.id_taxonref
             ELSE t1.id_parent
        END = idtaxonref
      )

    UNION ALL

    -- recursivity
    SELECT t2.id_taxonref
    FROM taxonomy.taxa_reference t2
    JOIN taxa_tree e ON t2.id_parent = e.id_taxonref
    CROSS JOIN params p
    WHERE t2.id_rank <= p.idrank_max
)
SELECT id_taxonref
FROM taxa_tree;
$$;
COMMENT ON FUNCTION taxonomy.pn_taxa_childs(INTEGER, BOOLEAN, BOOLEAN) IS 'Returns the child idtaxonref for the given idtaxonref argument, including it based on the included variable (DEFAULT = FALSE) and restricted (DEFAULT = FALSE) to child linked ranks';	


-----------------------------------------------------------------------------------------------
---#Return a table including the parent taxa, and ranks (and input idtaxonref if included is TRUE)
------------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION taxonomy.pn_taxa_parents(
	idtaxonref	INTEGER, 
	included	BOOLEAN DEFAULT FALSE
	)
 RETURNS TABLE(
 	id_taxonref	INTEGER)
 LANGUAGE sql
 STABLE
AS $function$
/*
	SELECT * FROM taxonomy.pn_taxa_parents(5813,True)
	SELECT *  FROM taxonomy.pn_taxa_parents(12595, True)
  	SELECT *  FROM taxonomy.pn_taxa_parents(12595, False)
 */
	WITH RECURSIVE 
	pn_taxa_parents  AS (
		SELECT t1.id_taxonref, t1.id_parent
		FROM taxonomy.taxa_reference t1
		WHERE t1.id_taxonref = idtaxonref
	UNION
		SELECT t2.id_taxonref, t2.id_parent
		FROM taxonomy.taxa_reference AS t2 
		INNER JOIN pn_taxa_parents e 
		ON t2.id_taxonref = e.id_parent
	)
	
	SELECT a.id_taxonref
	FROM pn_taxa_parents a
	WHERE
	CASE WHEN included = FALSE
		THEN a.id_taxonref <> idtaxonref
		ELSE a.id_taxonref IS NOT NULL
		END;
$function$;
COMMENT ON FUNCTION taxonomy.pn_taxa_parents(INTEGER, BOOLEAN) IS 'Return a table with parents taxa for the input idtaxonref, including the idtaxonref itself (included is True)';


-----------------------------------------------------------------------------------------------
---#Return a table with auto-generated names from taxonomy.taxa_reference (category 1 to 4)
---restricted to id_taxonref and childs (Default = NULL - all the nameset)
---DO NOT CREATE a new nameset, return a query based on taxa_reference allowing to create a new nameset
------------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION taxonomy.pn_taxa_refresh_nameset(idtaxonref INTEGER DEFAULT NULL)
 RETURNS TABLE(
 	original_name	TEXT,
	category		INTEGER,
	id_taxonref		INTEGER)
 LANGUAGE plpgsql
AS $function$

BEGIN
	SET LOCAL client_min_messages TO warning;
	DROP TABLE IF EXISTS tmp_taxa_reference;
	IF idtaxonref IS NULL THEN
		CREATE TEMP TABLE tmp_taxa_reference ON COMMIT DROP AS
			SELECT
				z.*
			FROM
				taxonomy.taxa_reference z;
	ELSE
		CREATE TEMP TABLE tmp_taxa_reference ON COMMIT DROP AS
			SELECT
				z.*
			FROM
				taxonomy.taxa_reference z
			INNER JOIN 
				taxonomy.pn_taxa_childs(idtaxonref, TRUE, TRUE) y 
			ON
				z.id_taxonref = y.id_taxonref;

			--SELECT * FROM taxonomy.taxa_reference z WHERE z.id_taxonref IN (SELECT y.id_taxonref FROM taxonomy.pn_taxa_childs(idtaxonref, TRUE, TRUE) y);

	END IF;
	
RETURN QUERY

    WITH 
		taxa_names AS (--compilation of auto-generated names derived from taxonomy.taxa_reference name
				SELECT  a.id_taxonref, concat_ws (chr(32), INITCAP(c.basename), b.basename, d.prefix, a.basename) AS taxa_name, a.authors
				FROM tmp_taxa_reference a
				INNER JOIN taxonomy.taxa_reference b ON b.id_taxonref = taxonomy.pn_taxa_getparent(a.id_parent, 21)
				INNER JOIN taxonomy.taxa_reference c ON c.id_taxonref = taxonomy.pn_taxa_getparent(a.id_parent, 14)
				INNER JOIN taxonomy.taxa_rank d ON d.id_rank = a.id_rank
				WHERE a.id_rank > 21 and a.id_rank < 31
			UNION ALL
				SELECT  a.id_taxonref, INITCAP(a.basename) AS taxa_name, a.authors
				FROM tmp_taxa_reference a
				WHERE a.id_rank < 21
			UNION ALL
				SELECT  a.id_taxonref, concat_ws (chr(32), INITCAP(c.basename), a.basename) AS taxa_name, a.authors
				FROM tmp_taxa_reference a
				INNER JOIN taxonomy.taxa_reference c ON c.id_taxonref = taxonomy.pn_taxa_getparent(a.id_parent, 14)
				WHERE a.id_rank = 21
			UNION ALL
				SELECT  a.id_taxonref, concat_ws (chr(32), INITCAP(b.basename), d.prefix, a.basename) AS taxa_name, a.authors
				FROM tmp_taxa_reference a
				INNER JOIN taxonomy.taxa_reference b ON b.id_taxonref = a.id_parent
				INNER JOIN taxonomy.taxa_rank d ON d.id_rank = a.id_rank
				WHERE a.id_rank = 31
		),
		taxa_others AS (--generate Concatenated name for infra-families taxa (ex: create taxa "Fabaceae - subfam. Mimosoideae" FROM "Mimosoideae")
				SELECT  a.id_taxonref, concat_ws (chr(32), INITCAP(c.basename), d.prefix, INITCAP(a.basename)) AS taxa_name, a.authors
				FROM tmp_taxa_reference a
				INNER JOIN taxonomy.taxa_reference c ON c.id_taxonref = taxonomy.pn_taxa_getparent(a.id_parent, 1)
				INNER JOIN taxonomy.taxa_rank d ON d.id_rank = a.id_rank
				WHERE a.id_rank < 7
			UNION ALL
				SELECT  a.id_taxonref, concat_ws (chr(32), INITCAP(c.basename), d.prefix, INITCAP(a.basename)) AS taxa_name, a.authors
				FROM tmp_taxa_reference a
				INNER JOIN taxonomy.taxa_reference c ON c.id_taxonref = taxonomy.pn_taxa_getparent(a.id_parent, 6)
				INNER JOIN taxonomy.taxa_rank d ON d.id_rank = a.id_rank
				WHERE a.id_rank IN (7, 8, 9)
			UNION ALL
				SELECT  a.id_taxonref, concat_ws (chr(32), INITCAP(c.basename), d.prefix, INITCAP(a.basename)) AS taxa_name, a.authors
				FROM tmp_taxa_reference a
				INNER JOIN taxonomy.taxa_reference c ON c.id_taxonref = taxonomy.pn_taxa_getparent(a.id_parent, 10)
				INNER JOIN taxonomy.taxa_rank d ON d.id_rank = a.id_rank
				WHERE a.id_rank IN (11, 12, 13)
			UNION ALL
				SELECT  a.id_taxonref, concat_ws (chr(32), INITCAP(c.basename), d.prefix, INITCAP(a.basename)) AS taxa_name, a.authors
				FROM tmp_taxa_reference a
				INNER JOIN taxonomy.taxa_reference c ON c.id_taxonref = taxonomy.pn_taxa_getparent(a.id_parent, 14)
				INNER JOIN taxonomy.taxa_rank d ON d.id_rank = a.id_rank
				WHERE a.id_rank IN (15, 16, 17, 18, 19)
		),
		ls_autonyms AS (--list of id_species to create autonyms (species with at least one infraspecific child)
				SELECT taxonomy.pn_taxa_getparent(a.id_parent, 21) AS id_species, id_rank
				FROM taxonomy.taxa_reference a
				WHERE a.id_rank > 21 AND a.id_rank < 31
				GROUP BY id_species,id_rank
		),
		taxa_autonyms AS (--create autonyms
				SELECT a.id_taxonref, 
				concat_ws (chr(32), initcap(c.basename), a.basename) AS species_name,
				concat_ws (chr(32), d.prefix, a.basename) AS infra_name,
				a.authors
				FROM taxonomy.taxa_reference a
				INNER JOIN taxonomy.taxa_reference c ON c.id_taxonref = taxonomy.pn_taxa_getparent(a.id_parent, 14)
				INNER JOIN ls_autonyms b ON a.id_taxonref = b.id_species
				INNER JOIN taxonomy.taxa_rank d ON b.id_rank = d.id_rank
				WHERE a.id_rank = 21
		),
		taxa_authors AS (--make a compilation including authors, even if no authors
				SELECT 1::integer code, a.id_taxonref, CONCAT_WS(CHR(32),a.taxa_name, a.authors) taxa_name 
				FROM taxa_names a
			UNION ALL
				SELECT 3::integer code, a.id_taxonref, CONCAT_WS(CHR(32),a.taxa_name, a.authors) taxa_name
				FROM taxa_others a
			UNION ALL
				SELECT 4::integer code, a.id_taxonref, CONCAT_WS(CHR(32),a.species_name, a.infra_name, a.authors) taxa_name 
				FROM taxa_autonyms a
			UNION ALL
				SELECT 4::integer code, a.id_taxonref, CONCAT_WS(CHR(32),a.species_name, a.authors, a.infra_name) taxa_name 
				FROM taxa_autonyms a
		),
		taxa_noauthors AS (--make a compilation of names without authors FOR those with authors
				SELECT 2::integer code, a.id_taxonref, a.taxa_name 
				FROM taxa_names a WHERE a.authors IS NOT NULL
			UNION ALL
				SELECT 3::integer code, a.id_taxonref, a.taxa_name
				FROM taxa_others a WHERE a.authors IS NOT NULL
			UNION ALL
				SELECT 4::integer code, a.id_taxonref, CONCAT_WS(CHR(32),a.species_name, a.infra_name) 
				FROM taxa_autonyms a WHERE a.authors IS NOT NULL
		),
		taxa_union AS (--make union of raw data
				SELECT code, b.id_taxonref::integer, b.taxa_name::text original_name FROM taxa_authors b
			UNION
				SELECT code, b.id_taxonref::integer, b.taxa_name::text original_name FROM taxa_noauthors b
		)
		--return the final union
		SELECT
			z.original_name,
	 		z.code,
	 		z.id_taxonref
		FROM 
			taxa_union z			
		GROUP BY z.code, z.id_taxonref, z.original_name;
END;
$function$;
COMMENT ON FUNCTION taxonomy.pn_taxa_refresh_nameset(INTEGER) IS 'Return a table with auto-generated names (category 1-4) from taxonomy_taxa_reference (restricted to id_taxonref and childs if id_taxonref is not null)';



-----------------------------------------------------------------------------------------------
---#Procedure to set as synonym from_idtaxonref to the taxon to_idtaxonref
------------------------------------------------------------------------------------------------

CREATE OR REPLACE PROCEDURE taxonomy.pn_taxa_set_synonymy(IN from_idtaxonref integer, IN to_idtaxonref integer, IN cat_synonym text DEFAULT 'Nomenclatural'::text)
 LANGUAGE plpgsql
AS $procedure$
/*
	call taxonomy.pn_taxa_set_synonymy (16875, 1577,'')
	call taxonomy.pn_taxa_set_synonymy (13570, 16609,'Taxinomic')
*/
DECLARE
	_idparent	INTEGER;
	from_idrank	INTEGER;
	to_idrank	INTEGER;
	_properties	TEXT;
	_idcategory	INTEGER;
BEGIN
--Check coherence of data before simulate merging
	--Verify that the from_idtaxonref is a valid taxaname
		SELECT a.id_taxonref, a.id_rank INTO from_idtaxonref, from_idrank FROM taxonomy.taxa_reference a  WHERE a.id_taxonref = from_idtaxonref;
		IF from_idtaxonref IS NULL THEN 
			RAISE invalid_parameter_value USING MESSAGE = 'Error : from_idtaxonref is not a valid reference' ;
		END IF;
	--Verify that the to_idtaxonref is a valid taxaname
		SELECT a.id_taxonref, a.id_rank INTO to_idtaxonref, to_idrank FROM taxonomy.taxa_reference a WHERE a.id_taxonref = to_idtaxonref;
		IF to_idtaxonref IS NULL THEN 
			RAISE invalid_parameter_value USING MESSAGE = 'Error: to_idtaxonref parameter is not a valid reference' ;
		END IF;	
	--Verify that ranks are equal when merge is apply on groups (including genus and above)	
		IF from_idrank <21 AND (to_idrank <> from_idrank) 	THEN
			RAISE invalid_parameter_value USING MESSAGE = 'Error : from_idtaxonref should be a sibling of to_idtaxonref - ranks are not compatible' ;
		END IF;	
	--Verify that the to_idataxonref is not a child of the from_idtaxonref
		SELECT a.id_taxonref INTO _idparent FROM taxonomy.pn_taxa_childs (from_idtaxonref) a WHERE a.id_taxonref = to_idtaxonref;
		IF _idparent IS NOT NULL THEN 
			RAISE invalid_parameter_value USING MESSAGE = 'Error : to_idtaxonref parameter is already a child of from_idtaxonref' ;
		END IF;

--DO UPDATE
	--update id_taxonref and category for names, set category for autogenerated names (category < 5)
		SELECT 4 + array_position(ARRAY['Nomenclatural', 'Taxinomic'], cat_synonym) INTO _idcategory;
		if _idcategory IS NULL THEN 
			_idcategory = 5;
		END IF;
	--update category for autogenerated names for linked childs
		UPDATE taxonomy.taxa_nameset
		SET category = _idcategory
		WHERE id_taxonref IN (SELECT id_taxonref FROM taxonomy.pn_taxa_childs(from_idtaxonref, TRUE, TRUE))
		AND category < 5 ;
	--update idtaxonref in taxa_nameset
		UPDATE taxonomy.taxa_nameset
		SET id_taxonref = to_idtaxonref
		WHERE id_taxonref = from_idtaxonref;
	--update properties
		UPDATE	taxonomy.taxa_reference u 
		SET	 properties = new_properties
		FROM
		(SELECT coalesce(a.properties, b.properties) AS new_properties
			FROM
			taxonomy.taxa_reference a, taxonomy.taxa_reference b
			WHERE a.id_taxonref = to_idtaxonref AND b.id_taxonref = from_idtaxonref) z
		WHERE	u.id_taxonref = to_idtaxonref;

	--fire trigger
	--update parent for childs
		UPDATE	taxonomy.taxa_reference u 
		SET	 id_parent = to_idtaxonref
		WHERE id_parent = from_idtaxonref;
	--finally delete the from_idtaxonref from taxa_reference table (delete childs and names on cascade with id_taxonref and id_parent)
	 	DELETE FROM	taxonomy.taxa_reference a 
	 	WHERE	a.id_taxonref = from_idtaxonref;
	 COMMIT;	
END;
$procedure$;
COMMENT ON PROCEDURE taxonomy.pn_taxa_set_synonymy(INTEGER, INTEGER, TEXT) IS 'Set from_idtaxonref as a synonym of to_idtaxonref';	




-------------------------------------------------------------
-------------------------------------------------------------
--MANAGE DATABASE, materialized view, view and triggers
-------------------------------------------------------------
-------------------------------------------------------------





-----------------------------------------------------------------------------------------------
--create a hierarchical table of taxa from taxa_reference (id_taxonref, id_family, id_genus, id_species, id_infra)
------------------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW taxonomy.taxa_hierarchy AS
	WITH 
	parent_species AS (
		SELECT id_parent FROM taxonomy.taxa_reference a
		WHERE id_rank >= 21
		GROUP BY id_parent
	),
	genus AS (
		SELECT id_parent AS id_parent_species, taxonomy.pn_taxa_getparent(id_parent, 14) AS id_genus 
		FROM parent_species
	),
	genus_species AS (
		SELECT
		CASE WHEN b.id_rank = 21 THEN b.id_taxonref
		ELSE taxonomy.pn_taxa_getparent(b.id_taxonref, 21)
		END AS id_species,
		CASE WHEN b.id_rank > 21 THEN b.id_taxonref
		ELSE NULL
		END AS id_infra,
		a.id_genus,
		b.id_taxonref
		FROM genus a
		INNER JOIN taxonomy.taxa_reference b 
		ON a.id_parent_species = b.id_parent	
	),
	genus_family AS ( 
		SELECT a.id_genus, taxonomy.pn_taxa_getparent(a.id_genus, 10) AS id_family
		FROM (SELECT id_genus FROM genus_species GROUP BY id_genus) a
	),
	family_genus_species AS ( 
		SELECT a.id_taxonref, b.id_family, a.id_genus, a.id_species, a.id_infra
		FROM genus_species a
		INNER JOIN genus_family b
		ON a.id_genus = b.id_genus
	)
	--SELECT * FROM genus_species
	SELECT a.id_family, a.id_genus, a.id_species, a.id_infra, b.* 
	FROM family_genus_species a
	INNER JOIN taxonomy.taxa_names b 
	ON a.id_taxonref = b.id_taxonref;
COMMENT ON VIEW taxonomy.taxa_names IS 'View to display hierarchy for any taxa in taxa_reference'
;















----------------------------------------------------------------------------------------------------
---Trigger function : check for taxon validity before updating or inserting in taxa_reference
-- generate errors in case of non-compliance with taxonomic or database rules
----------------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION taxonomy.pn_trigger_check_reference ()
RETURNS TRIGGER LANGUAGE plpgsql
AS $function$
DECLARE
	_taxanameparent		TEXT;
	_idrankparent		INTEGER;
	_basename			TEXT;
	_basenameparent		TEXT;
	_headline			TEXT;
	_ending				TEXT;
	_rank				TEXT;
	--_err_detail	TEXT;
BEGIN
		--New.basename = lower(NEW.basename);
		New.basename = trim(lower(REPLACE(New.basename,' ', '')));
		New.authors = trim(New.authors);

		_basename = COALESCE(NEW.basename::text,'');
		_headline = 'Editing is failed : integrity violation';
		OLD.id_parent = COALESCE(OLD.id_parent, 0);
		OLD.id_rank = COALESCE(OLD.id_rank, 0);
		OLD.basename = COALESCE(OLD.basename,'');

--check for the new basename if different
	IF _basename <> OLD.basename THEN
	--taxonomic : test the length of the newbasename (must be >=3)
		--SELECT * FROM taxonomy.pn_taxa_edit_reference (0, 'po', 'Birnbaum', 240, 21, False, False);
		--INSERT INTO taxonomy.taxa_reference (basename, id_parent, id_rank) values ('ab', 16184, 10);
			IF LENGTH(_basename) < 3 THEN
				RAISE EXCEPTION check_violation 
				USING message 	= _headline,
					  detail 	= 'Taxonomic rule - the minimum length of the taxon name is 3 characters',
					  hint 		= 'Modify the basename';
			END IF;
	--taxonomic : test the unicity of names for id_rank < 21
	--INSERT INTO taxonomy.taxa_reference (basename, id_parent, id_rank) values ('Guioa', 94, 14);
			IF NEW.id_rank < 21 THEN
				IF 
					(SELECT id_taxonref FROM taxonomy.taxa_reference a 
					 WHERE a.basename = lower(_basename))
				IS NOT NULL THEN 
					RAISE EXCEPTION check_violation 
					USING message 	= _headline,
						  detail 	= concat('Taxonomic rule - the basename {', _basename, '} already exists'),
						  hint 		= 'Check basename for the considered rank';
				END IF;
			END IF;

	--taxonomic : test the name ending, implicit for rank < = 13 (Subtribus)
		--SELECT * FROM taxonomy.pn_taxa_edit (0, 'family', 'authors', 16217, 10, False, False)
		--UPDATE taxonomy.taxa_reference SET basename = 'family' WHERE id_taxonref = 15;
		--INSERT INTO taxonomy.taxa_reference (basename, id_parent, id_rank) values ('family', 16184, 10);
			IF NEW.id_rank <= 13 THEN
				SELECT a.suffix, a.rank_name INTO _ending, _rank FROM taxonomy.taxa_rank a WHERE a.id_rank = NEW.id_rank;
				IF NOT NEW.basename LIKE '%' || _ending THEN
					RAISE EXCEPTION check_violation 
					USING message 	= _headline,
						  detail 	= concat('Taxonomic rule - the basename of a rank {', _rank, '} must be ending by ',  quote_literal(_ending)),
						  hint 		= 'Check that basename is written with the correct ending';
				END IF;
			END IF;

	END IF;

--check for the combination between new basename and new_id_parent
	IF _basename <> OLD.basename OR NEW.id_parent <> OLD.id_parent THEN
	--taxonomic : _basename must be different of the basename of parent
		-- SELECT * FROM taxonomy.pn_taxa_edit_reference (0, 'manihot', 'Birnbaum', 1577, 22, False, False)
		-- INSERT INTO taxonomy.taxa_reference (basename, id_parent, id_rank) values ('calvescens', 12701, 22);
		-- UPDATE taxonomy.taxa_reference SET basename = 'miconia' WHERE id_taxonref = 12701;
			IF 
				(SELECT id_taxonref FROM taxonomy.taxa_reference a 
				 WHERE a.id_taxonref = NEW.id_parent AND a.basename = _basename)
			IS NOT NULL THEN
				RAISE EXCEPTION check_violation 
				USING message 	= _headline,
					  detail 	= concat('Taxonomic rule - the basename {', _basename, '} cannot be similar to the parent basename'),
					  hint 		= 'Modify the basename of taxon or parent';
			END IF;
	--taxonomic : the combination of _basename and id_parent must be unique
		--exception already manage by unique_key (the combinaison (basename,id_parent) already exists)
		-- SELECT * FROM taxonomy.pn_taxa_edit_reference (0, 'manihot', 'Birnbaum', 240, 21, False, False)
		-- INSERT INTO taxonomy.taxa_reference (basename, id_parent, id_rank) values ('calvescens', 14830, 21);
		-- UPDATE taxonomy.taxa_reference SET basename = 'cristatum' WHERE id_taxonref = 6343;
		-- UPDATE taxonomy.taxa_reference SET id_parent = 750 WHERE id_taxonref = 14898;	
			IF 
				(SELECT id_taxonref FROM taxonomy.taxa_reference a 
				 WHERE a.basename = _basename AND a.id_parent = NEW.id_parent AND a.id_taxonref <> NEW.id_taxonref)
			<> NEW.id_taxonref THEN		
				SELECT a.name INTO _taxanameparent 
				FROM taxonomy.taxa_nameset a 
				WHERE a.id_taxonref = NEW.id_parent AND a.category = 1;
				RAISE EXCEPTION check_violation
				USING  message = _headline,
					   --detail = 'Integrity rule - the basename {' || _basename ||'} is already child of : ' || _taxanameparent,
					   detail = concat('Integrity rule - the basename {', _basename, '} is already child of : ', _taxanameparent),

					   hint   = 'Modify the basename or delete duplicate name';
			END IF;
	END IF;

--check the combination between newidparent and newidrank
if NEW.id_parent IS NOT NULL THEN
	IF NEW.id_parent <> OLD.id_parent OR NEW.id_rank <> OLD.id_rank THEN 
			--SELECT * FROM taxonomy.pn_taxa_edit_reference (0, 'trucaceae', 'Birnbaum', 240, 10, False, False)
			--UPDATE taxonomy.taxa_reference SET id_rank = 2  WHERE id_taxonref = 1575;
			--UPDATE taxonomy.taxa_reference SET id_parent = 6348  WHERE id_taxonref = 1575;
			SELECT a.id_rank INTO _idrankparent FROM taxonomy.taxa_reference a  WHERE a.id_taxonref = NEW.id_parent;
			IF 
				(SELECT b.id_rank FROM taxonomy.pn_ranks_children(_idrankparent) b WHERE b.id_rank = NEW.id_rank)
			IS NULL THEN
			--load the parent taxaname to display message
				SELECT a.name INTO _taxanameparent FROM taxonomy.taxa_nameset a 
				WHERE a.id_taxonref = NEW.id_parent AND a.category = 1;
			-- create message
				--_taxanameparent = concat('rank ', taxonomy.pn_ranks_name(_idrankparent), ' {',_taxanameparent,'}');
				RAISE EXCEPTION check_violation
				USING  message = _headline,
					   detail = concat('Taxonomic rule - the rank ', taxonomy.pn_ranks_name(_idrankparent), ' cannot be a parent of the rank ', taxonomy.pn_ranks_name(NEW.id_rank)),
					   hint   = concat('Modify the rank of the taxon {', _taxanameparent,'}');
			END IF;
	END IF;
END IF;

	--if id_parent is different, verify that the idtaxonref is not a child of the idparent
		--UPDATE taxonomy.taxa_reference SET id_parent = 12701, id_rank = 22, basename = 'magnifica'  WHERE id_taxonref = 14830;
			IF NEW.id_parent <> OLD.id_parent THEN 
				IF 
					(SELECT a.id_taxonref FROM taxonomy.pn_taxa_childs (NEW.id_taxonref) a WHERE a.id_taxonref = NEW.id_parent)
				IS NOT NULL THEN
					RAISE EXCEPTION check_violation
					USING  message = _headline,
						   detail = 'Integrity rule - The parent taxon is already a child of the taxon',
						   hint   = 'Modify the name of the taxon';
				END IF;
			END IF;

--check for integrity of published according to new.authors
		IF LENGTH(NEW.authors) <= 0 THEN
			NEW.authors = NULL;
		END IF;
		IF NEW.authors IS NULL THEN
			NEW.published = FALSE;
		END IF;
    RETURN NEW;
END $function$;
COMMENT ON FUNCTION taxonomy.pn_trigger_check_reference () IS 'call by triggers on taxa_reference update or insert, check the entry validity, according to database and taxonomics rules';



----------------------------------------------------------------------------------------------------
---function : pn_taxa_authors_score
-- return a table with authors score as the match account between the field authors and the key authors in metadata in the taxa_reference table 
----------------------------------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION taxonomy.pn_taxa_authors_score(idtaxonref integer)
 RETURNS TABLE(id_taxonref integer, matching_authors integer, total_authors integer, total_api integer, authors_score numeric)
 LANGUAGE sql
 STABLE
AS $function$

/*
SELECT (taxonomy.pn_taxa_authors_score(14838)).*
*/

	SELECT *,
	    COALESCE(
	      matching_authors::numeric 
	      / NULLIF(total_authors, 0), 
	      0
	    ) AS authors_score
	FROM	    
	(	
		SELECT
		    tr.id_taxonref,
		    COUNT(*) FILTER (WHERE norm_author = norm_tr_author) AS matching_authors,
		    COUNT(norm_author) AS total_authors,
		    COUNT(*) AS total_api	
		FROM 
			taxonomy.taxa_reference tr
		CROSS JOIN LATERAL 
			jsonb_each(tr.metadata) AS meta(key, value)
		CROSS JOIN LATERAL 
			(
			    SELECT 
					regexp_replace(lower(value ->> 'authors'), '[^[:alnum:]]', '', 'g')   AS norm_author,
					regexp_replace(lower(tr.authors),            '[^[:alnum:]]', '', 'g') AS norm_tr_author
			
			) normed
		WHERE 
			tr.id_taxonref = idtaxonref
		AND 
			value ? 'authors'
		GROUP BY 
			tr.id_taxonref
		);
$function$;
--
COMMENT ON FUNCTION taxonomy.pn_taxa_authors_score (INTEGER) IS 'Return a table with the matching result between authors and key authors from metadata';

----------------------------------------------------------------------------------------------------
---SET the triggers active on taxa_synonyms and taxa_reference
----------------------------------------------------------------------------------------------------
----------------------------------------------------------------------------------------------------


CREATE OR REPLACE FUNCTION taxonomy.pn_trigger_refresh_nameset ()
RETURNS TRIGGER LANGUAGE plpgsql
AS $function$
BEGIN
	--delete metadata if a new basename
	IF NEW.basename <> OLD.basename THEN
		UPDATE taxonomy.taxa_reference a
		SET metadata = NULL
		WHERE a.id_taxonref = NEW.id_taxonref;
	ELSIF NEW.authors <> OLD.authors THEN
	--update authors_score if authors is different
			UPDATE taxonomy.taxa_reference a
			SET metadata = jsonb_set(metadata, '{score,authors_score}', (z.authors_score::text)::jsonb, false)
			FROM 
				(SELECT 
					id_taxonref, authors_score
				FROM taxonomy.pn_taxa_authors_score(NEW.id_taxonref)
				) z
			WHERE a.id_taxonref = NEW.id_taxonref;
	END IF;


	--delete auto-names (category < 5) in the table taxa_nameset
	DELETE FROM taxonomy.taxa_nameset a
	WHERE a.id_taxonref IN (SELECT y.id_taxonref FROM taxonomy.pn_taxa_childs(NEW.id_taxonref, TRUE, TRUE) y)
	AND a.category < 5 ;
	--insert new auto-names in the table taxa_nameset
	INSERT INTO taxonomy.taxa_nameset (name, category, id_taxonref)
	SELECT
		z.original_name,
		z.category,
		z.id_taxonref
	FROM 
		taxonomy.pn_taxa_refresh_nameset(NEW.id_taxonref) z			
	GROUP BY z.category, z.id_taxonref, z.original_name
	ON CONFLICT (_keyname) DO UPDATE
	SET name = EXCLUDED.name, category = EXCLUDED.category, id_taxonref = EXCLUDED.id_taxonref;
	RETURN NEW;
END $function$;
--
COMMENT ON FUNCTION taxonomy.pn_trigger_refresh_nameset () IS 'call by trigger_after_update, to create the nameset related to the id_taxonref';



--ALTER TABLE taxonomy.taxa_reference ENABLE TRIGGER trigger_before_update 
--for checking validty of datas before updating or insering a new taxa
CREATE OR REPLACE TRIGGER trigger_before_update
	BEFORE INSERT OR UPDATE OF basename, id_rank, id_parent, id_taxonref
	ON taxonomy.taxa_reference FOR EACH ROW  
	EXECUTE FUNCTION taxonomy.pn_trigger_check_reference();

--for checking validity of datas before updating or insering a new taxa
CREATE OR REPLACE TRIGGER trigger_after_update
	AFTER INSERT OR UPDATE OF basename, authors, id_rank, id_parent, id_taxonref
	ON taxonomy.taxa_reference FOR EACH ROW
	EXECUTE FUNCTION taxonomy.pn_trigger_refresh_nameset();





INSERT INTO taxonomy.taxa_nameset (name, category, id_taxonref)
SELECT
	z.original_name,
	z.category,
	z.id_taxonref
FROM 
	taxonomy.pn_taxa_refresh_nameset() z;



--for refreshing by trigger the autogenerated names (from category 1 to 4) in the table taxonomy.taxa_nameset relative to NEW.id_taxonref
--CREATE OR REPLACE FUNCTION taxonomy.pn_trigger_refresh_nameset ()
--RETURNS TRIGGER LANGUAGE plpgsql
--AS $function$
--
--/*
--	select * from taxonomy.pn_taxa_childs (1038, true, true)
--	select * from test_nameset where id_taxonref IN (select id_taxonref from taxonomy.pn_taxa_childs (1038, true, true))
--	select * from taxonomy.taxa_nameset where id_taxonref IN (select id_taxonref from taxonomy.pn_taxa_childs (1038, true, true))
-- */
--	BEGIN
--		--delete the autogenerated names from taxa_nameset
--		DELETE FROM taxonomy.taxa_nameset
--		WHERE id_taxonref IN (SELECT id_taxonref FROM taxonomy.pn_taxa_childs(NEW.id_taxonref, TRUE, TRUE))
--		AND category < 5 ;
--
--		--create and insert the new autogenerated names into taxa_nameset
--			-- 1 = référence - taxa_authors
--			-- 2 = référence - taxa noauthors
--			-- 3 = référence - alternative names (with and without authors, ex variant in genus, subgenus)
--			-- 4 = référence - autonyms (with and without authors)
--		WITH 
--			taxa_reference AS (--select childs names impacted by a new basename, authors or hierarchy
--			SELECT * FROM 
--				taxonomy.taxa_reference
--				WHERE id_taxonref IN (SELECT id_taxonref FROM taxonomy.pn_taxa_childs(NEW.id_taxonref, TRUE, TRUE))
--			),
--			taxa_names AS (--compilation of auto-generated names derived from taxonomy.taxa_reference name
--					SELECT  a.id_taxonref, concat_ws (chr(32), INITCAP(c.basename), b.basename, d.prefix, a.basename) AS taxa_name, a.authors
--					FROM taxa_reference a
--					INNER JOIN taxonomy.taxa_reference b ON b.id_taxonref = taxonomy.pn_taxa_getparent(a.id_parent, 21)
--					INNER JOIN taxonomy.taxa_reference c ON c.id_taxonref = taxonomy.pn_taxa_getparent(a.id_parent, 14)
--					INNER JOIN taxonomy.taxa_rank d ON d.id_rank = a.id_rank
--					WHERE a.id_rank > 21 and a.id_rank < 31
--				UNION
--					SELECT  a.id_taxonref, INITCAP(a.basename) AS taxa_name, a.authors
--					FROM taxa_reference a
--					WHERE a.id_rank < 21
--				UNION
--					SELECT  a.id_taxonref, concat_ws (chr(32), INITCAP(c.basename), a.basename) AS taxa_name, a.authors
--					FROM taxa_reference a
--					INNER JOIN taxonomy.taxa_reference c ON c.id_taxonref = taxonomy.pn_taxa_getparent(a.id_parent, 14)
--					WHERE a.id_rank = 21
--				UNION
--					SELECT  a.id_taxonref, concat_ws (chr(32), INITCAP(b.basename), d.prefix, a.basename) AS taxa_name, a.authors
--					FROM taxa_reference a
--					INNER JOIN taxonomy.taxa_reference b ON b.id_taxonref = a.id_parent
--					INNER JOIN taxonomy.taxa_rank d ON d.id_rank = a.id_rank
--					WHERE a.id_rank = 31
--			),
--			taxa_others AS (--generate Concatenated name for infra-families taxa (ex: create taxa "Fabaceae - subfam. Mimosoideae" FROM "Mimosoideae")
--					SELECT  a.id_taxonref, concat_ws (chr(32), INITCAP(c.basename), d.prefix, a.basename) AS taxa_name, a.authors
--					FROM taxa_reference a
--					INNER JOIN taxonomy.taxa_reference c ON c.id_taxonref = taxonomy.pn_taxa_getparent(a.id_parent, 1)
--					INNER JOIN taxonomy.taxa_rank d ON d.id_rank = a.id_rank
--					WHERE a.id_rank < 7
--				UNION
--					SELECT  a.id_taxonref, concat_ws (chr(32), INITCAP(c.basename), d.prefix, a.basename) AS taxa_name, a.authors
--					FROM taxa_reference a
--					INNER JOIN taxonomy.taxa_reference c ON c.id_taxonref = taxonomy.pn_taxa_getparent(a.id_parent, 6)
--					INNER JOIN taxonomy.taxa_rank d ON d.id_rank = a.id_rank
--					WHERE a.id_rank IN (7,8, 9)
--				UNION
--					SELECT  a.id_taxonref, concat_ws (chr(32), INITCAP(c.basename), d.prefix, a.basename) AS taxa_name, a.authors
--					FROM taxa_reference a
--					INNER JOIN taxonomy.taxa_reference c ON c.id_taxonref = taxonomy.pn_taxa_getparent(a.id_parent, 10)
--					INNER JOIN taxonomy.taxa_rank d ON d.id_rank = a.id_rank
--					WHERE a.id_rank IN (11, 12, 13)
--				UNION
--					SELECT  a.id_taxonref, concat_ws (chr(32), INITCAP(c.basename), d.prefix, a.basename) AS taxa_name, a.authors
--					FROM taxa_reference a
--					INNER JOIN taxonomy.taxa_reference c ON c.id_taxonref = taxonomy.pn_taxa_getparent(a.id_parent, 14)
--					INNER JOIN taxonomy.taxa_rank d ON d.id_rank = a.id_rank
--					WHERE a.id_rank IN (15, 16, 17, 18, 19)
--			),
--			ls_autonyms AS (--list of id_species to create autonyms (species with at least one infraspecific child)
--					SELECT taxonomy.pn_taxa_getparent(a.id_parent, 21) AS id_species, id_rank
--					FROM taxonomy.taxa_reference a
--					WHERE a.id_rank > 21 AND a.id_rank < 31
--					GROUP BY id_species,id_rank
--			),
--			taxa_autonyms AS (--create autonyms
--					SELECT a.id_taxonref, 
--					concat_ws (chr(32), initcap(c.basename), a.basename) AS species_name,
--					concat_ws (chr(32), d.prefix, a.basename) AS infra_name,
--					a.authors
--					FROM taxonomy.taxa_reference a
--					INNER JOIN taxonomy.taxa_reference c ON c.id_taxonref = taxonomy.pn_taxa_getparent(a.id_parent, 14)
--					INNER JOIN ls_autonyms b ON a.id_taxonref = b.id_species
--					INNER JOIN taxonomy.taxa_rank d ON b.id_rank = d.id_rank
--					WHERE a.id_rank = 21
--			),
--			taxa_authors AS (--make a compilation including authors, even if no authors
--					SELECT 1::integer code, a.id_taxonref, CONCAT_WS(CHR(32),a.taxa_name, a.authors) taxa_name 
--					FROM taxa_names a
--				UNION 
--					SELECT 3::integer code, a.id_taxonref, CONCAT_WS(CHR(32),a.taxa_name, a.authors) taxa_name
--					FROM taxa_others a
--				UNION 
--					SELECT 4::integer code, a.id_taxonref, CONCAT_WS(CHR(32),a.species_name, a.infra_name, a.authors) taxa_name 
--					FROM taxa_autonyms a
--				UNION 
--					SELECT 4::integer code, a.id_taxonref, CONCAT_WS(CHR(32),a.species_name, a.authors, a.infra_name) taxa_name 
--					FROM taxa_autonyms a
--			),
--			taxa_noauthors AS (--make a compilation of names without authors FOR those with authors
--					SELECT 2::integer code, a.id_taxonref, a.taxa_name 
--					FROM taxa_names a WHERE a.authors IS NOT NULL
--				UNION 
--					SELECT 3::integer code, a.id_taxonref, a.taxa_name
--					FROM taxa_others a WHERE a.authors IS NOT NULL
--				UNION
--					SELECT 4::integer code, a.id_taxonref, CONCAT_WS(CHR(32),a.species_name, a.infra_name) 
--					FROM taxa_autonyms a WHERE a.authors IS NOT NULL
--	--UNION
--	--SELECT
--	--CASE 
--	--	WHEN b.category = 'Nomenclatural' THEN 5
--	--	WHEN b.category = 'Taxinomic' THEN 6
--	--	WHEN b.category = 'Common' THEN 7
--	--	WHEN b.category = 'Orthographic' THEN 8
--	--	ELSE 9
--	--END ::integer code, 
--	--b.id_taxonref::integer, b.synonym::text original_name
--	--FROM taxonomy.taxa_synonym b
--	--				
--			),
--			taxa_union AS (--make union of raw data
--					SELECT code, b.id_taxonref::integer, b.taxa_name::text original_name FROM taxa_authors b
--				UNION
--					SELECT code, b.id_taxonref::integer, b.taxa_name::text original_name FROM taxa_noauthors b
--			)
--			--return the final union
--
--			--insert into taxonomy.taxa_nameset	
--			INSERT INTO taxonomy.taxa_nameset (name, category, id_taxonref)
--			SELECT
--				z.original_name,
--		 		z.code,
--		 		z.id_taxonref
--			FROM 
--				taxa_union z			
--			GROUP BY z.code, z.id_taxonref, z.original_name
--			ON CONFLICT (_keyname) DO UPDATE
--			SET name = EXCLUDED.name, category = EXCLUDED.category, id_taxonref = EXCLUDED.id_taxonref;
--RETURN NEW;
--	END
--  $function$;


















