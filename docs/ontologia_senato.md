@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix dc: <http://purl.org/dc/elements/1.1/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix vann: <http://purl.org/vocab/vann/> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix osr: <http://dati.senato.it/osr/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<http://senaopendata.senato.intranet/neologism/osr> a owl:Ontology;
    dcterms:title "Ontologia del Senato della Repubblica";
    dcterms:description "La presente ontologia consente la rappresentazione dei dati relativi all'attività parlamentare e ai Senatori, ed è coordinata con la corrispondente <a href=\"http://dati.camera.it/ocd/reference_document/\">Ontologia della Camera dei Deputati</a>.";
    dc:license "http://creativecommons.org/licenses/by/3.0/";
    dcterms:modified "2013-02-13"^^xsd:date;
    vann:preferredNamespaceUri "http://dati.senato.it/osr/";
    vann:preferredNamespacePrefix "osr";
    foaf:homepage <http://senaopendata.senato.intranet/neologism/osr.html>;
    dcterms:created "2012-12-19"^^xsd:date;
    dcterms:partOf <http://senaopendata.senato.intranet/neologism>;
    dcterms:type <http://purl.org/adms/assettype/Ontology>;
    dcterms:status <http://purl.org/adms/status/UnderDevelopment>;
    dc:creator <http://senaopendata.senato.intranet/neologism/osr#Senato%20della%20Repubblica> .

<http://senaopendata.senato.intranet/neologism/osr#ttl>
    dcterms:FileFormat <>;
    dcterms:license <http://creativecommons.org/licenses/by/3.0/> .

<http://senaopendata.senato.intranet/neologism/osr#rdf>
    dcterms:FileFormat <>;
    dcterms:license <http://creativecommons.org/licenses/by/3.0/> .

<http://senaopendata.senato.intranet/neologism/osr#Senato%20della%20Repubblica> a foaf:Person;
    foaf:name "Senato della Repubblica";
    foaf:homepage <http://dati.senato.it> .

osr:Atto a rdfs:Class, owl:Class;
    rdfs:label "Atto";
    rdfs:comment "Questa class rappresenta un qualsiasi documento oggetto di attività parlamentare generica." .

osr:Documento a rdfs:Class, owl:Class;
    rdfs:label "Documento";
    rdfs:comment "Questa classe rappresenta un qualsiasi documento non legislativo.";
    rdfs:subClassOf osr:Atto .

osr:SindacatoIspettivo a rdfs:Class, owl:Class;
    rdfs:label "SindacatoIspettivo";
    rdfs:comment "Questa classe modella un documento relativo ad attività di sindacato ispettivo";
    rdfs:subClassOf osr:Atto .

osr:Ddl a rdfs:Class, owl:Class;
    rdfs:label "Ddl";
    rdfs:comment "Questa classe rappresenta un Disegno di Legge ed e' la classe fondamentale per rappresentare tutto l'iter legislativo.";
    rdfs:subClassOf osr:Atto .

osr:Iniziativa a rdfs:Class, owl:Class;
    rdfs:label "Iniziativa";
    rdfs:comment "Le istanza di questa classe rappresentano singole iniziative parlamentari." .

osr:Assegnazione a rdfs:Class, owl:Class;
    rdfs:label "Assegnazione";
    rdfs:comment "Questa classe modella l'evento di assegnazione di un DDL a una data Commissione." .

osr:Denominazione a rdfs:Class, owl:Class;
    rdfs:label "Denominazione";
    rdfs:comment "Questa classe rappresenta la denominazione (e le sue caratteristiche temporali) dei gruppi Parlamentari." .

osr:Relatore a rdfs:Class, owl:Class;
    rdfs:label "Relatore";
    rdfs:comment "Questa classe modella il ruolo di relatore di un DDL per un Senatore." .

osr:Senatore a rdfs:Class, owl:Class;
    rdfs:label "Senatore";
    rdfs:comment "Questa classe modella un Senatore." .

osr:OggettoTrattazione a rdfs:Class, owl:Class;
    rdfs:label "OggettoTrattazione";
    rdfs:comment "Questa classe modella l'oggetto della trattazione nel corso di una seduta di Assemblea o di Commissione." .

osr:Intervento a rdfs:Class, owl:Class;
    rdfs:label "Intervento";
    rdfs:comment "Questa e' la classe che modella un intervento di un Senatore su un dato DDL in una data seduta di una Commissione o di Assemblea." .

osr:Procedura a rdfs:Class, owl:Class;
    rdfs:label "Procedura";
    rdfs:comment "Questa classe modella una procedura non legislativa." .

osr:Afferenza a rdfs:Class, owl:Class;
    rdfs:label "Afferenza";
    rdfs:comment "La classe consente di specificare afferenze di istanze di tipo Senatore a istanze di tipo Commissione o ConsiglioDiPresidenza, consentendone di specificare la carica (presidente, vicepresidente)." .

osr:Votazione a rdfs:Class, owl:Class;
    rdfs:label "Votazione";
    rdfs:comment "Le istanze di questa classe si riferiscono alle votazioni in Aula svolte mediante sistema elettronico." .

osr:SedutaAssemblea a rdfs:Class, owl:Class;
    rdfs:label "SedutaAssemblea";
    rdfs:comment "Questa classe rappresenta la seduta dell'assemblea." .

osr:SedutaCommissione a rdfs:Class, owl:Class;
    rdfs:label "SedutaCommissione";
    rdfs:comment "Rappresenta la seduta di una Commissione. OCD, non distingue tra sedute di organi diversi, il Senato potendo esporre dati diversi per ogni singola seduta di una commissione, ha bisogno di una specializzazione di tale classe." .

osr:Commissione a rdfs:Class, owl:Class;
    rdfs:label "Commissione";
    rdfs:comment "Questa classe modella una Commissione Parlamentare." .

osr:ConsiglioDiPresidenza a rdfs:Class, owl:Class;
    rdfs:label "ConsiglioDiPresidenza";
    rdfs:comment "Questa classe modella il Consiglio di Presidenza." .

osr:FaseIter a rdfs:Class, owl:Class;
    rdfs:label "Fase Iter";
    rdfs:comment "Questa classe modella una fase di un Ddl nel suo Iter." .

osr:IterDdl a rdfs:Class, owl:Class;
    rdfs:label "Iter Ddl";
    rdfs:comment "Questa classe rappresenta tutto l'iter legislativo di un Ddl nella sua interezza." .

osr:iniziativa a rdf:Property;
    rdfs:label "Iniziativa";
    rdfs:comment "Questa proprietà lega un Atto alla sua relativa Iniziativa";
    rdfs:domain osr:Atto;
    rdfs:range osr:Iniziativa .

osr:assegnazione a rdf:Property;
    rdfs:label "Assegnazione";
    rdfs:comment "Questa proprietà modella una assegnazione di un DDL alla relativa istanza di assegnazione.";
    rdfs:domain osr:Ddl;
    rdfs:range osr:Assegnazione .

osr:relatore a rdf:Property;
    rdfs:label "Relatore";
    rdfs:comment "Permette di specificare il Relatore di un DDL.";
    rdfs:domain osr:Ddl;
    rdfs:range osr:Relatore .

osr:relativoA a rdf:Property;
    rdfs:label "Relativo a";
    rdfs:comment "Questa proprietà consente di legare una Procedura o un Oggetto trattazione al relativo Atto oppure una FaseIter al corrispettivo Ddl.";
    rdfs:domain
        osr:Procedura,
        osr:OggettoTrattazione,
        osr:FaseIter;
    rdfs:range
        osr:Atto,
        osr:Documento,
        osr:SindacatoIspettivo,
        osr:Ddl .

osr:senatore a rdf:Property;
    rdfs:label "Senatore";
    rdfs:comment "Questa proprietà consente di specificare il legame tra una Iniziativa, o un ruolo di Relatore, alla rispettiva istanza della classe Senatore.";
    rdfs:domain
        osr:Iniziativa,
        osr:Relatore;
    rdfs:range osr:Senatore .

osr:interviene a rdf:Property;
    rdfs:label "Interviene";
    rdfs:comment "Questa proprietà consente di legare un Senatore ai suoi Interventi.";
    rdfs:domain osr:Senatore;
    rdfs:range osr:Intervento .

osr:favorevole a rdf:Property;
    rdfs:label "Favorevole";
    rdfs:comment "Questa proprietà lega una istanza di Votazione con il Senatore che abbia espresso voto favorevole.";
    rdfs:domain osr:Votazione;
    rdfs:range osr:Senatore .

osr:contrario a rdf:Property;
    rdfs:label "Contrario";
    rdfs:comment "Questa proprietà consente di legare una Votazione con un Senatore che abbia espresso voto contrario. ";
    rdfs:domain osr:Votazione;
    rdfs:range osr:Senatore .

osr:astenuto a rdf:Property;
    rdfs:label "Astenuto";
    rdfs:comment "Questa proprietà consente di specificare l'astensione di un Senatore per una data Votazione.";
    rdfs:domain osr:Votazione;
    rdfs:range osr:Senatore .

osr:inCongedoMissione a rdf:Property, owl:DatatypeProperty;
    rdfs:label
        "In Congedo o Missione",
        "In congedo o in missione";
    rdfs:comment
        "Questa proprietà consente di legare un Senatore che si sia assentato giustificatamente durante una determinata Votazione.",
        "Il numero di senatori in congedo o in missione durante una votazione.";
    rdfs:domain osr:Votazione;
    rdfs:range
        osr:Senatore,
        xsd:integer .

osr:seduta a rdf:Property;
    rdfs:label "Seduta";
    rdfs:comment "Questa proprietà lega una istanza della classe Votazione o Intervento a una data Seduta.";
    rdfs:domain
        osr:Intervento,
        osr:Votazione;
    rdfs:range
        osr:SedutaAssemblea,
        osr:SedutaCommissione .

osr:oggetto a rdf:Property;
    rdfs:label "Oggetto";
    rdfs:comment "Consente di specificare il legame esistente tra una Votazione, un Intervento e le rispettivi Procedure o Oggetto Trattazione.";
    rdfs:domain
        osr:Votazione,
        osr:Intervento;
    rdfs:range
        osr:Procedura,
        osr:OggettoTrattazione .

osr:commissione a rdf:Property;
    rdfs:label "Commissione";
    rdfs:comment "Consente di specificare per una Seduta di Commissione o per una Afferenza, la relativa Commissione di interesse.";
    rdfs:domain
        osr:SedutaAssemblea,
        osr:Afferenza;
    rdfs:range osr:Commissione .

osr:organo a rdf:Property;
    rdfs:label "Organo";
    rdfs:comment "Questa proprietà consente genericamente di legare una istanza di Afferenza con un dato organo (Consiglio di Presidenza, Commissione)";
    rdfs:domain osr:Afferenza;
    rdfs:range osr:ConsiglioDiPresidenza .

osr:assorbimento a rdf:Property;
    rdfs:label "Assorbimento";
    rdfs:comment "Questa proprietà lega un Ddl al suo Iter nel caso in cui il Ddl sia stato assorbito.";
    rdfs:domain osr:IterDdl;
    rdfs:range osr:Ddl .

osr:testoUnificato a rdf:Property;
    rdfs:label "Testo Unificato";
    rdfs:comment "Questa proprietà lega un Ddl al suo Iter, nel caso in cui il Ddl sia stato unificato.";
    rdfs:domain osr:IterDdl;
    rdfs:range osr:Ddl .

osr:stralcio a rdf:Property;
    rdfs:label "Stralcio";
    rdfs:comment "Nel caso in cui in Ddl sia stato stralciato, questa proprietà consente di specificarlo nel suo Iter.";
    rdfs:domain osr:IterDdl;
    rdfs:range osr:Ddl .

osr:fase a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Fase";
    rdfs:comment
        "questa proprietà consente di specificare tutte le fasi che costituiscono un determinato IterDdl.",
        "Questa proprietà e' la concatenazione del ramo con il numero fase.";
    rdfs:domain
        osr:IterDdl,
        osr:Ddl;
    rdfs:range
        osr:Ddl,
        xsd:string .

osr:URLTesto a rdf:Property;
    rdfs:label "URL Testo";
    rdfs:comment "questa proprietà consente di specificare l'URL del testo di un atto.";
    rdfs:domain
        osr:Atto,
        osr:Documento,
        osr:SindacatoIspettivo,
        osr:Ddl .

osr:astenuti a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Astenuti";
    rdfs:comment "Il numero di senatori astenuti durante una votazione";
    rdfs:domain osr:Votazione;
    rdfs:range xsd:integer .

osr:carica a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Carica";
    rdfs:comment "Questa proprietà consente di specificare la carica ricoperta da un Senatore in una afferenza a un gruppo parlametare, o a una commissione";
    rdfs:domain
        osr:Senatore,
        osr:Afferenza;
    rdfs:range xsd:string .

osr:categoriaCommissione a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Categoria Commissione";
    rdfs:comment "Consente di specificare la categoria di una Commissione.";
    rdfs:domain osr:Commissione;
    rdfs:range xsd:string .

osr:contrari a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Contrari";
    rdfs:comment "Il numero di senatori che hanno espresso voto contrario durante una Votazione.";
    rdfs:domain osr:Votazione;
    rdfs:range xsd:integer .

osr:dataAssegnazione a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Data Assegnazione";
    rdfs:comment "La data di assegnazione di un Ddl a una Commissione.";
    rdfs:domain osr:Assegnazione;
    rdfs:range xsd:date .

osr:dataComunicazione a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Data Comunicazione";
    rdfs:comment "La data in cui l'inizio di un mandato senato e' stato comunicato.";
    rdfs:range xsd:date .

osr:dataConvalida a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Data convalida";
    rdfs:comment "La data di convalida del mandato Senato.";
    rdfs:range xsd:date .

osr:dataCostituzione a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Data di Costituzione";
    rdfs:comment "Data di costituzione di un gruppo parlamentare.";
    rdfs:range xsd:date .

osr:dataNomina a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Data Nomina";
    rdfs:comment "La data di nomina di un Relatore o di un Senatore a inizio mandato.";
    rdfs:domain osr:Relatore;
    rdfs:range xsd:date .

osr:dataPresentazione a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Data di Presentazione";
    rdfs:comment "La data di presentazione di un atto.";
    rdfs:domain
        osr:Atto,
        osr:Documento,
        osr:SindacatoIspettivo,
        osr:Ddl;
    rdfs:range xsd:date .

osr:dataSeduta a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Data Seduta";
    rdfs:comment "La data di una Seduta di Assemblea o di Commissione.";
    rdfs:domain
        osr:SedutaAssemblea,
        osr:SedutaCommissione;
    rdfs:range xsd:date .

osr:dataStatoDdl a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Data Stato Ddl";
    rdfs:comment "La data dell'ultimo aggiornamento di stato di un Ddl.";
    rdfs:domain osr:Ddl;
    rdfs:range xsd:date .

osr:diMinoranza a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Di Minoranza";
    rdfs:comment "1 Se un relatore e' di minoranza, 0 altrimenti.";
    rdfs:domain osr:Relatore;
    rdfs:range xsd:integer .

osr:esito a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Esito";
    rdfs:comment "L'esito di una Votazione (su Ddl o su un Sindacato Ispettivo)";
    rdfs:domain
        osr:Votazione,
        osr:SindacatoIspettivo;
    rdfs:range xsd:string .

osr:favorevoli a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Favorevoli";
    rdfs:comment "Il numero di senatori che hanno espresso voto favorevole durante una votazione";
    rdfs:domain osr:Votazione;
    rdfs:range xsd:integer .

osr:fine a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Fine";
    rdfs:comment "Proprietà che consente di specificare la fine di un periodo temporale.";
    rdfs:domain osr:Afferenza;
    rdfs:range xsd:dateTime .

osr:idDdl a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Identificativo Ddl";
    rdfs:comment "Rappresenta un identificativo comune a tutti i Ddl aventi lo stesso Iter.";
    rdfs:domain
        osr:Ddl,
        osr:IterDdl;
    rdfs:range xsd:integer .

osr:inizio a rdf:Property, owl:DatatypeProperty;
    rdfs:label "inizio";
    rdfs:comment "Rappresenta l'inizio di un periodo temporale.";
    rdfs:domain
        osr:Afferenza,
        osr:Denominazione;
    rdfs:range xsd:date .

osr:legislatura a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Legislatura";
    rdfs:comment "Indica la legislatura per una serie di classi del vocabolario.";
    rdfs:domain
        osr:Atto,
        osr:Documento,
        osr:SindacatoIspettivo,
        osr:Ddl,
        osr:SedutaAssemblea,
        osr:SedutaCommissione,
        osr:Procedura,
        osr:OggettoTrattazione,
        osr:ConsiglioDiPresidenza,
        osr:Votazione;
    rdfs:range xsd:date .

osr:maggioranza a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Maggioranza";
    rdfs:comment "Rappresenta in termini numerici la maggioranza richiesta durante una votazione.";
    rdfs:domain osr:Votazione;
    rdfs:range xsd:integer .

osr:natura a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Natura";
    rdfs:comment "La natura di un Ddl.";
    rdfs:domain osr:Ddl;
    rdfs:range rdfs:Literal .

osr:numero a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Numero";
    rdfs:comment "Il numero di una Votazione o di un Atto.";
    rdfs:domain
        osr:Votazione,
        osr:Atto;
    rdfs:range xsd:integer .

osr:numeroDoc a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Numero Documento";
    rdfs:comment "Il numero di un documento generico.";
    rdfs:domain osr:Documento;
    rdfs:range xsd:integer .

osr:numeroFase a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Numero Fase";
    rdfs:comment "Numero Fase di un Ddl.";
    rdfs:domain osr:Ddl;
    rdfs:range xsd:string .

osr:numeroFaseCompatto a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Numero Fase Compatto";
    rdfs:comment "Versione su cui e' possibile stabilire un ordinamento numerico della proprietà numeroFase.";
    rdfs:domain osr:Ddl;
    rdfs:range xsd:string .

osr:numeroLegale a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Numero Legale";
    rdfs:comment "Numero Legale richiesto durante una Votazione";
    rdfs:domain osr:Votazione;
    rdfs:range xsd:integer .

osr:numeroRomano a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Numero Romano";
    rdfs:comment "Numero del Documento in notazione numerica romana.";
    rdfs:domain osr:Documento;
    rdfs:range xsd:string .

osr:numeroSeduta a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Numero Seduta";
    rdfs:comment "Numero della Seduta";
    rdfs:domain
        osr:SedutaAssemblea,
        osr:SedutaCommissione;
    rdfs:range xsd:integer .

osr:ordinale a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Ordinale";
    rdfs:comment "Il numero ordinale di una commissione.";
    rdfs:domain osr:Commissione;
    rdfs:range xsd:string .

osr:presentatoTrasmesso a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Presentato o Trasmesso";
    rdfs:comment "Se un Ddl è stato presentato o trasmesso.";
    rdfs:domain osr:Ddl;
    rdfs:range xsd:string .

osr:presenti a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Presenti";
    rdfs:comment "Il numero di senatori presenti durante una votazione";
    rdfs:domain osr:Votazione;
    rdfs:range xsd:integer .

osr:primoFirmatario a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Primo Firmatario";
    rdfs:comment "Indica se l'iniziativa collegata è una prima firma.";
    rdfs:domain osr:Iniziativa;
    rdfs:range xsd:string .

osr:progrIter a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Progressivo Iter";
    rdfs:comment "Il progressivo del Ddl nell'ambito dell'iter.";
    rdfs:domain osr:FaseIter;
    rdfs:range xsd:integer .

osr:progressivoIter a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Progressivo Iter";
    rdfs:domain osr:Ddl;
    rdfs:range xsd:integer .

osr:ramo a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Ramo";
    rdfs:comment "Ramo del Parlamento";
    rdfs:domain osr:Atto;
    rdfs:range xsd:string .

osr:sede a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Sede";
    rdfs:comment "Sede dell'assegnazione: referente, dirigente, consultiva.";
    rdfs:domain osr:Assegnazione;
    rdfs:range xsd:string .

osr:sottotitolo a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Sotto titolo";
    rdfs:comment "Sotto titolo di una Commissione.";
    rdfs:domain osr:Commissione;
    rdfs:range xsd:string .

osr:statoDdl a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Stato Ddl";
    rdfs:comment "Stato del Ddl.";
    rdfs:domain osr:Ddl;
    rdfs:range xsd:string .

osr:statoDoc a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Stato Documento";
    rdfs:comment "Stato del Documento";
    rdfs:domain osr:Documento;
    rdfs:range xsd:string .

osr:suffissoNumeroDoc a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Suffisso Numero Documento";
    rdfs:comment "Il suffisso del numero del documento.";
    rdfs:domain osr:Documento;
    rdfs:range xsd:string .

osr:tipo a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Tipo Atto";
    rdfs:comment "Tipo dell'Atto.";
    rdfs:domain osr:Atto;
    rdfs:range xsd:string .

osr:tipoCommissione a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Tipo Commissione";
    rdfs:comment "Tipo della Commissione durante un'assegnazione.";
    rdfs:domain osr:Assegnazione;
    rdfs:range xsd:string .

osr:tipoDoc a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Tipo del Documento";
    rdfs:domain osr:Documento;
    rdfs:range xsd:string .

osr:tipoFineMandato a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Tipo del Fine mandato";
    rdfs:comment "Es: decesso.";
    rdfs:range xsd:string .

osr:tipoIniziativa a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Tipo Iniziativa";
    rdfs:comment "Tipo dell'iniziativa legislativa.";
    rdfs:domain osr:Iniziativa;
    rdfs:range xsd:string .

osr:tipoMandato a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Tipo del mandato";
    rdfs:comment "Specifica se elettivo o di diritto.";
    rdfs:range xsd:string .

osr:tipoRelatore a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Tipo Relatore";
    rdfs:comment "Tipologia del relatore.";
    rdfs:domain osr:Relatore;
    rdfs:range xsd:string .

osr:tipoSeduta a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Tipo Seduta";
    rdfs:comment "Tipologia della Seduta";
    rdfs:domain osr:Votazione;
    rdfs:range xsd:string .

osr:tipoVotazione a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Tipo di Votazione";
    rdfs:comment "Se elettronica palese o segreta.";
    rdfs:domain osr:Votazione;
    rdfs:range xsd:string .

osr:titolo a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Titolo";
    rdfs:comment "Riferibile ad ogni entità con un titolo.";
    rdfs:domain
        osr:Ddl,
        osr:Procedura,
        osr:Documento,
        osr:Commissione,
        osr:Denominazione,
        osr:ConsiglioDiPresidenza;
    rdfs:range xsd:string .

osr:votanti a rdf:Property, owl:DatatypeProperty;
    rdfs:label "Votanti";
    rdfs:comment "Numero dei votanti";
    rdfs:domain osr:Votazione;
    rdfs:range xsd:integer .

osr:gruppo a rdf:Property;
    rdfs:label "Gruppo";
    rdfs:comment "Lega una adesione gruppo a un gruppo parlamentare" .

osr:denominazione a rdf:Property;
    rdfs:label "Denominazione";
    rdfs:comment "Attribuisce una o più denominazioni a un gruppo parlamentare";
    rdfs:range osr:Denominazione .

osr:mandato a rdf:Property;
    rdfs:label "mandato";
    rdfs:comment "Lega un senatore ai suoi mandati.";
    rdfs:domain osr:Senatore .

osr:dataAggiuntaFirma a rdf:Property, owl:DatatypeProperty;
    rdfs:label "DataAggiuntaFirma";
    rdfs:comment "La data in cui è stata aggiunta la firma per la presentazione di un DDL";
    rdfs:domain osr:Iniziativa;
    rdfs:range xsd:string .

osr:dataRitiroFirma a rdf:Property, owl:DatatypeProperty;
    rdfs:label "DataRitiroFirma";
    rdfs:comment "La data in cui è stata ritirata la firma per la presentazione di un DDL";
    rdfs:domain osr:Iniziativa;
    rdfs:range xsd:string .
