# Tender radar

Stranica koja jednom dnevno prikuplja otvorene objave o nabavkama iz domaćih i međunarodnih izvora i omogućava pretragu i filtriranje. Čuva samo osnovne podatke o objavi (datum objave, ugovorni organ, naziv, rok) i link na originalnu objavu. Tendersku dokumentaciju ne preuzima.

## Postavljanje na GitHub (jednom, oko 15 minuta)

1. Na github.com klikni New repository. Ime: `tender-radar`. Vidljivost: Public. Ništa drugo ne označavaj. Klikni Create repository.
2. Na stranici novog repozitorija klikni link „uploading an existing file“. Otvori raspakovani folder, označi sve u njemu (Ctrl+A) i prevuci u prozor preglednika. Prevlači se sadržaj foldera, ne sam folder. Klikni Commit changes.
3. Folder `.github` se ne može prevući, jer GitHub pri prevlačenju preskače sve što počinje tačkom. Klikni Add file, zatim Create new file. U polje za naziv upiši `.github/workflows/daily.yml`, zalijepi sadržaj istog fajla iz raspakovanog foldera i klikni Commit changes.
4. Za interne izvore otvori Settings, zatim Secrets and variables, zatim Actions. Klikni New repository secret. Name: `TR_PASSPHRASE`. Secret: šifra koju sam izabereš. Klikni Add secret. Bez ovog koraka alat radi, ali interne izvore ne preuzima.
5. Otvori Settings, zatim Pages. Pod „Build and deployment“ za Source izaberi „GitHub Actions“.
6. Otvori karticu Actions. Lijevo izaberi „Osvježi tendere“, desno klikni Run workflow, pa zeleno dugme Run workflow.
7. Nakon 4 do 5 minuta stranica je na adresi `https://TVOJE-KORISNICKO-IME.github.io/tender-radar/`. Tačan link stoji u Settings, Pages.

Od tada se podaci osvježavaju sami, svaki dan oko 5:30 po sarajevskom vremenu.

## Kasnije izmjene

Izmijenjen fajl se prenosi preko Add file, Upload files; fajl s istim imenom zamijeni stari. Fajl iz foldera `collectors` prenosi se tako što se prevuče cijeli folder `collectors` ili se prvo otvori taj folder na GitHubu. Sitne izmjene i fajl `.github/workflows/daily.yml` mijenjaju se klikom na olovku. Izmjena se na stranici vidi tek nakon sljedećeg pokretanja „Osvježi tendere“ (ručno iz kartice Actions ili sutra ujutro).

Folder `data` se nikad ne prenosi ručno. U njemu alat čuva podatke i evidenciju o tome kad je koju objavu prvi put vidio.

## Korištenje

Filteri su lijevo: moje oznake, ključne riječi, izvor, država, regija u BiH, vrsta ugovora, ko može ponuditi, sektor, oblast po CPV kodu, rok, procijenjena vrijednost i vrsta naručioca. Broj uz svaku opciju pokazuje koliko objava ona daje uz ostale izabrane filtere. Dugme „Očisti sve filtere“ na vrhu menija vraća prikaz svih objava. Dugme „Objavljeno danas“ iznad liste pokazuje objave koje su se pojavile u današnjem osvježavanju; broj na dugmetu kaže koliko ih je, a te objave su u listi na svijetloplavoj podlozi. Objava objavljena prije više od sedmice koju alat tek sada vidi (npr. nova država ili novi izvor) ne računa se kao današnja. Opcije u filterima su poredane po abecedi; e-Nabavke BiH i Bosna i Hercegovina su uvijek prve, a „Ostalo“ zadnje. Na mobitelu i tabletu filteri se otvaraju dugmetom „Filteri“ pored pretrage; broj u zagradi kaže koliko je filtera uključeno.

Ključne riječi se odvajaju zarezom i dovoljan je korijen riječi („energetsk“ nalazi i „energetska“ i „energetske“). Kvačice nisu bitne. Nazivi na ćirilici prikazuju se latinicom (preslovljeno, nije prevod), a izvorni naziv se vidi kad se mišem stane na naziv. Kvačica „traži i istoznačnice na drugim jezicima“ (uključena sama od sebe) dodaje istu riječ na drugim jezicima: „okoliš“ nalazi i „environment“, „Umwelt“ i „životna sredina“. Ispod polja piše šta je dodano.

Uz svaku objavu su dugmad „Pratim“ i „Sakrij“. Praćene i sakrivene objave biraju se pod „Moje oznake“; sakrivene se više ne prikazuju dok ih ne vratiš. Stranica pamti i koje si podatke zadnji put vidio, pa iznad liste piše koliko je objava novih od zadnje posjete. Oznake, zadnja posjeta i profili čuvaju se u pregledniku u kojem su napravljeni i ne dijele se s kolegama. Za drugi uređaj koristi izvoz i uvoz u prozoru „Sačuvaj profil“; „Kopiraj link“ prenosi samo filtere.

Dugme „Pošalji“ uz objavu priprema poruku s naslovom, ključnim podacima i linkom na objavu. Primaoca upišeš u prozoru ili tek u samoj poruci. Stranica sama ne šalje ništa; poruku šalješ ti. „Otvori u Outlooku“ preuzme gotovu poruku s tabelom (.eml fajl): klikni preuzeti fajl i Outlook je otvori spremnu za slanje. „Otvori e-mail“ i „Otvori u Gmailu“ otvaraju poruku s podacima kao tekstom, jer link koji otvara poruku ne može prenijeti tabelu; tabela se pri tome kopira sama, pa je u poruci zalijepiš sa Ctrl+V preko redova s podacima. Stranica pamti način koji si zadnji put koristio. „Kopiraj tabelu“ kopira tabelu za Word ili chat. Adrese koje upišeš pamte se samo u tom pregledniku.

Sektor (energija, okoliš, ostalo) i „ko može ponuditi“ (organizacija, pojedinac, ostalo, nepoznato) alat određuje sam, pa su približni. Sektor ide po CPV kodu gdje ga izvor daje i po riječima u nazivu. Nabavke naftnih derivata (gorivo, lož ulje, maziva) ne računaju se u energiju, a nabavke uglja, peleta, plina, električne i toplotne energije se računaju. Ko može ponuditi uzima se iz izvora kad ga on navodi (Svjetska banka), javne nabavke (e-Nabavke, TED, EU) vode se kao pozivi za organizacije, a kod ostalih odlučuju riječi u nazivu, na primjer „individual consultant“ ili oznaka postupka RFP. „Ostalo“ su pozivi otvoreni i firmama i pojedincima te pozivi za nevladine organizacije. Pravila za oboje su u fajlu `index.html`.

Filter po procijenjenoj vrijednosti radi u KM. Iznosi u drugim valutama preračunavaju se po dnevnoj kursnoj listi ECB-a, a 1 EUR je 1,95583 KM. Vrijednost objavljuju e-Nabavke, Svjetska banka i dio objava TED-a i EU portala.

Oznaka „rok pomjeren“ pojavi se kad se rok objave promijeni između dva osvježavanja. Na TED-u je ispravka nova objava s novim brojem, pa se tamo pomjeren rok vidi kao nova objava.

Oznaka „novo“ stoji uz objave koje su stigle poslije tvoje zadnje posjete. Pri prvoj posjeti stoji uz objave koje je alat prvi put vidio danas ili jučer.

## Javni pozivi (grantovi)

Prekidač „Tenderi / Javni pozivi“ iznad liste dijeli objave na nabavke (posao za firmu) i javne pozive za grantove i sredstva. Svaki dio pamti svoje filtere. Javne pozive daju EU programi (Horizon Europe, LIFE, Erasmus+ i drugi), UNDP-ovi pozivi za prijedloge, CzechAid, Fond za zaštitu okoliša FBiH, Eko fond RS, FMRPO, i Mreža mira.

AI javne pozive ocjenjuje za CETEOR i za REIC: ocjena od 0 do 3, za koga je poziv (filter „AI: za koga je poziv“) i kratko obrazloženje s tim ko smije aplicirati. Opis REIC-a je u `config.json`, dio `ai`, polje `profile_reic`; provjeri ga i dopuni. Ko smije aplicirati AI procjenjuje iz naziva poziva, pa uslove uvijek provjeri u samom pozivu.

## DevelopmentAid (isključen)

DevelopmentAid je isključen: pretraga tendera i grantova preko API-ja se plaća dodatno uz članarinu, a uslovi stranice i zaštita od robota ne dozvoljavaju automatsko preuzimanje sa stranice. Kod ostaje u fajlu `collectors/developmentaid.py`. Ako se pretraga jednom plati, izvor se uključuje dodavanjem `"developmentaid"` u listu `MODULES` u `collect.py` i brisanjem unosa `DA` iz liste `excluded` u `config.json`; ključ ide u GitHub secret `DA_API_KEY`.

## AI: ocjena za CETEOR i Pitaj AI

Ocjena za CETEOR: pri svakom osvježavanju AI pročita nove objave i svakoj da ocjenu od 0 do 3 (3 jako relevantno, 2 moguće, 1 slabo, 0 nije za nas) i jednu rečenicu obrazloženja. Na stranici su filter „AI ocjena za CETEOR“, poredak „AI ocjena, najbolje prvo“ i oznaka „AI 3/3“ uz objavu. AI ocjenjuje po opisu firme u `config.json` (dio `ai`, polje `profile`); što je opis tačniji, ocjene su bolje. Svaka objava se ocjenjuje jednom. Pri prvom osvježavanju ocijeni se do 2.000 objava, a ostatak sljedeći dan. Objave internih izvora (GIZ, OSCE) ne šalju se AI servisu dok se u `config.json` ne postavi `"include_private": true`.

Pitaj AI: dugme pored pretrage. Napišeš običnim jezikom šta tražiš, a AI postavi filtere; „Vrati prethodne“ u poruci vraća stare. Prvi put stranica traži API ključ i pamti ga samo u tom pregledniku.

Postavljanje (jednom):

1. Na console.anthropic.com napravi račun. U dijelu Billing uplati kredit (npr. 5 USD) i postavi mjesečni limit potrošnje.
2. Pod API keys klikni Create key i kopiraj ključ.
3. Na GitHubu otvori Settings, zatim Secrets and variables, zatim Actions i klikni New repository secret. Name: `ANTHROPIC_API_KEY`, Secret: ključ. Klikni Add secret.
4. U fajlu `.github/workflows/daily.yml` (olovka) ispod reda s `TR_PASSPHRASE` mora stajati red `ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}`, uvučen isto kao red iznad.
5. Za Pitaj AI isti ključ (ili poseban) upiši na stranici kad je zatraži.

AI prijevod: naslovi koji nisu na bosanskom, hrvatskom, srpskom, crnogorskom ili engleskom (npr. makedonski, švedski, češki, francuski) dobiju kratak prijevod na engleski. Prijevod je ispod originalnog naslova, ljubičastom bojom i s oznakom EN; pretraga ga uzima u obzir, a ima ga i u CSV-u i u poruci „Pošalji“. Svaki naslov se provjerava jednom. Interni izvori se ne prevode dok se ne postavi `"include_private": true`. Prijevod se isključuje s `"translate": false` u dijelu `ai` u `config.json`.

Cijena: model je Claude Haiku 4.5 (1 USD na milion ulaznih i 5 USD na milion izlaznih tokena). Prvo ocjenjivanje svih objava košta oko 1 USD, a prva provjera naslova za prijevod manje od 0,50 USD; poslije toga oboje košta nekoliko centi dnevno. Jedno pitanje u Pitaj AI košta manje od jednog centa. Bez ključa sve ostalo radi kao i prije.

## Izvori

| Izvor | Šta se prikuplja | Način |
|---|---|---|
| e-Nabavke BiH | Sva otvorena obavještenja o nabavci (robe, usluge, radovi) | Zvanični open data API Agencije za javne nabavke |
| e-Nabavki Sjeverna Makedonija | Aktuelni oglasi; zadano samo usluge (u `config.json`, dio `mk`, mogu se dodati robe i radovi) | Javna tabela oglasa na e-nabavki.gov.mk |
| TED (EU) | Zapadni Balkan i Hrvatska: svi ugovori. EU institucije, međunarodne organizacije i razvojne agencije, te švedska agencija za zaštitu okoliša (Naturvårdsverket): usluge | Zvanični API |
| EU Funding & Tenders | Otvoreni i najavljeni tenderi EU institucija | Zvanični API |
| Svjetska banka | Svi otvoreni pozivi u svijetu | Zvanični API |
| UNDP | Sve otvorene objave u svijetu | Zvanični RSS feed |
| EBRD | Samo pozivi objavljeni na ebrd.com (malo ih je) | Lista na stranici |
| RCC | Svi otvoreni pozivi; poziv koji ne imenuje državu vodi se pod šest zemalja Zapadnog Balkana | Stranica „Open Calls“ |
| Expertise France | Sve otvorene nabavke | Javna pretraga platforme PLACE |
| GIZ (interni) | Svi otvoreni pozivi s GIZ-ove platforme, i manji tenderi kojih nema na TED-u | Javna lista na ausschreibungen.giz.de |
| OSCE (interni) | Svi otvoreni tenderi sekretarijata, institucija i misija | Javna lista na procurement.osce.org |
| CzechAid | Tenderi i pozivi za dotacije Češke razvojne agencije | Vijesti i lista dotacija na czechaid.gov.cz |
| EU programi (grantovi) | Otvoreni i najavljeni pozivi EU programa | Zvanični API (isti kao EU Funding & Tenders) |
| Fond za zaštitu okoliša FBiH | Otvoreni javni pozivi i konkursi; pozivi koje Fond objavi kao zatvorene se izostavljaju | Stranice kategorija na fzofbih.org.ba |
| Mreža mira | Pozivi za projekte, grantove i programe koje mreža prenosi za organizacije iz BiH | RSS feed kategorije (sadržaj pod licencom CC BY-SA 3.0) |
| Eko fond RS | Javni konkursi za tekuću godinu | Stranice konkursa na ekofondrs.org |
| FMRPO | Javni pozivi i konkursi ministarstva | RSS feed kategorije na fmrpo.gov.ba |

Dvanaest izvora nije uključeno i treba ih pregledati ručno. DevelopmentAid: pretraga preko API-ja se plaća dodatno, a stranica ne dozvoljava automatsko preuzimanje. Nacionalni portali Hrvatske (EOJN RH) i Srbije (Portal javnih nabavki) u robots.txt zabranjuju automatski pristup; hrvatske nabavke iznad EU praga ipak stižu preko TED-a. Albanska agencija (APP) ima dnevni CSV izvoz, ali ga robots.txt zabranjuje robotima. Za portale Crne Gore (CEJN) i Kosova (e-Prokurimi) nije pronađen javni popis tendera koji se može čitati bez prijave. Naturvårdsverket svoje nabavke vodi na Mercellu, koji je aplikacija bez javnog popisa; njegove nabavke usluga iznad EU praga stižu preko TED-a. UNGM u uslovima korištenja zabranjuje preuzimanje sadržaja u druge sisteme bez pisane dozvole. UNOPS i FAO objavljuju preko UNGM-a i nemaju vlastitu javnu listu. EBRD-ov portal ECEPP, na kojem je većina tendera iz EBRD projekata, odbija automatski pristup, kao i sajtovi Energy Community i WWF Adria.

Na e-Nabavkama se ne prikupljaju javni pozivi za usluge iz Aneksa II, direktni sporazumi i poništeni postupci.

## Interni izvori (pod šifrom)

GIZ u uslovima korištenja svoje platforme dozvoljava upotrebu rezultata pretrage samo interno i zabranjuje prenos trećim licima. OSCE bez pisane dozvole dozvoljava upotrebu sadržaja samo za lične i obrazovne svrhe. Zato se objave ta dva izvora ne pišu u javni fajl. Alat ih šifrira šifrom iz GitHub secreta `TR_PASSPHRASE` i sprema u `data/private.json`, a stranica ih prikaže tek kad se ista šifra unese preko dugmeta „Interni izvori“ u zaglavlju.

Šifra se pamti u pregledniku u koji je unesena, dok se tamo ne klikne „Zaključaj u ovom pregledniku“. Ko nema šifru, vidi sve ostalo, a interne izvore vidi kao zaključane. Šifru daj samo ljudima iz firme.

Objavu iz internog izvora dugmetom „Pošalji“ šalji samo kolegama u firmi. Prozor na to upozori, a poruka i tabela nose napomenu da se objava ne prosljeđuje dalje.

Zaštita je jaka koliko i šifra: uzmi bar četiri nasumične riječi ili 16 znakova. Šifra se mijenja izmjenom secreta; sljedeće osvježavanje šifrira podatke novom šifrom, a svi je moraju ponovo unijeti. Stare verzije šifriranog fajla ostaju u historiji repozitorija i otvaraju se starom šifrom.

Bilo koji drugi izvor može se prebaciti u interni dio upisom njegovog ključa u listu `private_sources` u fajlu `config.json`, na primjer `["EF", "EBRD"]`.

## Kad nešto ne radi

Dugme „Izvori“ na stranici pokazuje stanje svakog izvora. Kad izvor zakaže, stranica zadržava njegove zadnje uspješno preuzete objave i ispisuje grešku. Stranice izvora se povremeno mijenjaju, pa kolektor tada treba popraviti: tekst greške iz prozora „Izvori“ je dovoljan za dijagnozu.

Ako podaci nisu osvježeni duže od jednog dana, otvori karticu Actions. GitHub zna pauzirati zakazane zadatke u repozitoriju koji dugo nema aktivnosti. Tada na vrhu kartice stoji dugme za ponovno uključivanje.

## Postavke

Fajl `config.json` određuje šta se prikuplja. U dijelu `ted` su države za koje se s TED-a uzimaju sve objave i nazivi agencija čije se usluge prate (oznaka `@SE` znači: samo naručilac iz te države). U dijelu `mk` su vrste ugovora koje se preuzimaju iz Sjeverne Makedonije. U listi `private_sources` su ključevi izvora koji se vode kao interni, uz one koji su to po svojoj prirodi (GIZ, OSCE). U dijelu `excluded` su izvori koji su namjerno izostavljeni i razlog. Izmjena važi od sljedećeg osvježavanja.

Izvor se isključuje brisanjem njegovog naziva iz liste `MODULES` na vrhu fajla `collect.py`.

## Napomena o korištenju podataka

Stranica je javna za svakoga ko ima link, ali je označena tako da je pretraživači ne indeksiraju. Prikazuje samo naziv, naručioca, datume i link na originalnu objavu. Platforma PLACE (izvor za Expertise France) i sajtovi ebrd.com i undp.org u uslovima korištenja imaju opće klauzule koje ograničavaju preuzimanje sadržaja. Ako to želiš izbjeći, prebaci te izvore u interni dio ili ih isključi.

## Tehnički

`collect.py` pokreće kolektore iz foldera `collectors` i piše `data/tenders.json`, `data/status.json` i šifrirani `data/private.json`. `ai_score.py` je AI ocjena objava. `index.html` je cijela stranica. `.github/workflows/daily.yml` je dnevni raspored. Pravila za pisanje novog kolektora su u `collectors/CONTRACT.md`.

Lokalno pokretanje: `pip install -r requirements.txt`, zatim `python collect.py`. Samo jedan izvor: `python collect.py --only TED`. Interni izvori se lokalno preuzimaju samo ako je postavljena varijabla okruženja `TR_PASSPHRASE`.
