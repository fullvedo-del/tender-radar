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

Filteri su lijevo: moje oznake, ključne riječi, izvor, država, regija u BiH, vrsta ugovora, ko može ponuditi, sektor, oblast po CPV kodu, rok, procijenjena vrijednost i vrsta naručioca. Broj uz svaku opciju pokazuje koliko objava ona daje uz ostale izabrane filtere. Dugme „Očisti sve filtere“ na vrhu menija vraća prikaz svih objava.

Ključne riječi se odvajaju zarezom i dovoljan je korijen riječi („energetsk“ nalazi i „energetska“ i „energetske“). Kvačice nisu bitne. Nazivi na ćirilici prikazuju se latinicom (preslovljeno, nije prevod), a izvorni naziv se vidi kad se mišem stane na naziv.

Uz svaku objavu su dugmad „Pratim“ i „Sakrij“. Praćene i sakrivene objave biraju se pod „Moje oznake“; sakrivene se više ne prikazuju dok ih ne vratiš. Stranica pamti i koje si podatke zadnji put vidio, pa iznad liste piše koliko je objava novih od zadnje posjete. Oznake, zadnja posjeta i profili čuvaju se u pregledniku u kojem su napravljeni i ne dijele se s kolegama. Za drugi uređaj koristi izvoz i uvoz u prozoru „Sačuvaj profil“; „Kopiraj link“ prenosi samo filtere.

Dugme „Pošalji“ uz objavu otvara gotovu poruku u tvom programu za poštu: naslov, ključni podaci i link na objavu. Primaoca upišeš u prozoru ili tek u samoj poruci. Stranica sama ne šalje ništa; poruku šalješ ti. Ko poštu čita u Gmailu u pregledniku, u istom prozoru klikne „Otvori u Gmailu“, i stranica to zapamti za sljedeći put. Podaci su u poruci upisani kao tekst, jer link koji otvara poruku ne može prenijeti tabelu. Pravu tabelu daje „Kopiraj tabelu“: zalijepi je sa Ctrl+V u poruku, Word ili chat. Adrese koje upišeš pamte se samo u tom pregledniku.

Sektor (energija, okoliš, ostalo) i „ko može ponuditi“ (organizacija, pojedinac, ostalo, nepoznato) alat određuje sam, pa su približni. Sektor ide po CPV kodu gdje ga izvor daje i po riječima u nazivu. Nabavke naftnih derivata (gorivo, lož ulje, maziva) ne računaju se u energiju, a nabavke uglja, peleta, plina, električne i toplotne energije se računaju. Ko može ponuditi uzima se iz izvora kad ga on navodi (Svjetska banka), javne nabavke (e-Nabavke, TED, EU) vode se kao pozivi za organizacije, a kod ostalih odlučuju riječi u nazivu, na primjer „individual consultant“ ili oznaka postupka RFP. „Ostalo“ su pozivi otvoreni i firmama i pojedincima te pozivi za nevladine organizacije. Pravila za oboje su u fajlu `index.html`.

Filter po procijenjenoj vrijednosti radi u KM. Iznosi u drugim valutama preračunavaju se po dnevnoj kursnoj listi ECB-a, a 1 EUR je 1,95583 KM. Vrijednost objavljuju e-Nabavke, Svjetska banka i dio objava TED-a i EU portala.

Oznaka „rok pomjeren“ pojavi se kad se rok objave promijeni između dva osvježavanja. Na TED-u je ispravka nova objava s novim brojem, pa se tamo pomjeren rok vidi kao nova objava.

Oznaka „novo“ stoji uz objave koje su stigle poslije tvoje zadnje posjete. Pri prvoj posjeti stoji uz objave koje je alat prvi put vidio danas ili jučer.

## Izvori

| Izvor | Šta se prikuplja | Način |
|---|---|---|
| e-Nabavke BiH | Sva otvorena obavještenja o nabavci (robe, usluge, radovi) | Zvanični open data API Agencije za javne nabavke |
| TED (EU) | Zapadni Balkan: svi ugovori. EU institucije, međunarodne organizacije i razvojne agencije: usluge | Zvanični API |
| EU Funding & Tenders | Otvoreni i najavljeni tenderi EU institucija | Zvanični API |
| Svjetska banka | Svi otvoreni pozivi u svijetu | Zvanični API |
| UNDP | Sve otvorene objave u svijetu | Zvanični RSS feed |
| EBRD | Samo pozivi objavljeni na ebrd.com (malo ih je) | Lista na stranici |
| RCC | Svi otvoreni pozivi; poziv koji ne imenuje državu vodi se pod šest zemalja Zapadnog Balkana | Stranica „Open Calls“ |
| Expertise France | Sve otvorene nabavke | Javna pretraga platforme PLACE |
| GIZ (interni) | Svi otvoreni pozivi s GIZ-ove platforme, i manji tenderi kojih nema na TED-u | Javna lista na ausschreibungen.giz.de |
| OSCE (interni) | Svi otvoreni tenderi sekretarijata, institucija i misija | Javna lista na procurement.osce.org |

Šest izvora nije uključeno i treba ih pregledati ručno. UNGM u uslovima korištenja zabranjuje preuzimanje sadržaja u druge sisteme bez pisane dozvole. UNOPS i FAO objavljuju preko UNGM-a i nemaju vlastitu javnu listu. EBRD-ov portal ECEPP, na kojem je većina tendera iz EBRD projekata, odbija automatski pristup, kao i sajtovi Energy Community i WWF Adria.

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

Fajl `config.json` određuje šta se prikuplja. U dijelu `ted` su države za koje se s TED-a uzimaju sve objave i nazivi agencija čije se usluge prate. U listi `private_sources` su ključevi izvora koji se vode kao interni, uz one koji su to po svojoj prirodi (GIZ, OSCE). U dijelu `excluded` su izvori koji su namjerno izostavljeni i razlog. Izmjena važi od sljedećeg osvježavanja.

Izvor se isključuje brisanjem njegovog naziva iz liste `MODULES` na vrhu fajla `collect.py`.

## Napomena o korištenju podataka

Stranica je javna za svakoga ko ima link, ali je označena tako da je pretraživači ne indeksiraju. Prikazuje samo naziv, naručioca, datume i link na originalnu objavu. Platforma PLACE (izvor za Expertise France) i sajtovi ebrd.com i undp.org u uslovima korištenja imaju opće klauzule koje ograničavaju preuzimanje sadržaja. Ako to želiš izbjeći, prebaci te izvore u interni dio ili ih isključi.

## Tehnički

`collect.py` pokreće kolektore iz foldera `collectors` i piše `data/tenders.json`, `data/status.json` i šifrirani `data/private.json`. `index.html` je cijela stranica. `.github/workflows/daily.yml` je dnevni raspored. Pravila za pisanje novog kolektora su u `collectors/CONTRACT.md`.

Lokalno pokretanje: `pip install -r requirements.txt`, zatim `python collect.py`. Samo jedan izvor: `python collect.py --only TED`. Interni izvori se lokalno preuzimaju samo ako je postavljena varijabla okruženja `TR_PASSPHRASE`.
