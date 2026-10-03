# Tender radar

Stranica koja jednom dnevno prikuplja otvorene objave o nabavkama iz domaćih i međunarodnih izvora i omogućava pretragu i filtriranje. Čuva samo osnovne podatke o objavi (datum objave, ugovorni organ, naziv, rok) i link na originalnu objavu. Tendersku dokumentaciju ne preuzima.

## Postavljanje na GitHub (jednom, oko 10 minuta)

1. Na github.com klikni New repository. Ime: `tender-radar`. Vidljivost: Public. Ništa drugo ne označavaj. Klikni Create repository.
2. Na stranici novog repozitorija klikni link „uploading an existing file“. Otvori raspakovani folder, označi sve u njemu (Ctrl+A) i prevuci u prozor preglednika. Prevlači se sadržaj foldera, ne sam folder. Klikni Commit changes.
3. Provjeri da u listi fajlova postoji folder `.github`. Ako ga nema, vidi „Ako folder .github nije prenesen“ niže.
4. Otvori Settings, zatim Pages. Pod „Build and deployment“ za Source izaberi „GitHub Actions“.
5. Otvori karticu Actions. Lijevo izaberi „Osvježi tendere“, desno klikni Run workflow, pa zeleno dugme Run workflow.
6. Nakon 4 do 5 minuta stranica je na adresi `https://TVOJE-KORISNICKO-IME.github.io/tender-radar/`. Tačan link stoji u Settings, Pages.

Od tada se podaci osvježavaju sami, svaki dan oko 5:30 po sarajevskom vremenu.

### Ako folder .github nije prenesen

U repozitoriju klikni Add file, zatim Create new file. U polje za naziv upiši `.github/workflows/daily.yml`. Otvori isti fajl iz raspakovanog foldera u Notepadu, kopiraj cijeli sadržaj, zalijepi i klikni Commit changes.

## Korištenje

Filteri su lijevo: moje oznake, ključne riječi, izvor, država, regija u BiH, vrsta ugovora, ko može ponuditi, sektor, oblast po CPV kodu, rok, procijenjena vrijednost i vrsta naručioca. Broj uz svaku opciju pokazuje koliko objava ona daje uz ostale izabrane filtere. Dugme „Očisti sve filtere“ na vrhu menija vraća prikaz svih objava.

Ključne riječi se odvajaju zarezom i dovoljan je korijen riječi („energetsk“ nalazi i „energetska“ i „energetske“). Kvačice nisu bitne. Nazivi na ćirilici prikazuju se latinicom (preslovljeno, nije prevod), a izvorni naziv se vidi kad se mišem stane na naziv.

Uz svaku objavu su dugmad „Pratim“ i „Sakrij“. Praćene i sakrivene objave biraju se pod „Moje oznake“; sakrivene se više ne prikazuju dok ih ne vratiš. Stranica pamti i koje si podatke zadnji put vidio, pa iznad liste piše koliko je objava novih od zadnje posjete. Oznake, zadnja posjeta i profili čuvaju se u pregledniku u kojem su napravljeni i ne dijele se s kolegama. Za drugi uređaj koristi izvoz i uvoz u prozoru „Sačuvaj profil“; „Kopiraj link“ prenosi samo filtere.

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

Tri izvora nisu uključena i treba ih pregledati ručno. UNGM u uslovima korištenja zabranjuje preuzimanje sadržaja u druge sisteme bez pisane dozvole. EBRD-ov portal ECEPP, na kojem je većina tendera iz EBRD projekata, odbija automatski pristup. Energy Community automatski pristup odbija zaštitom od robota.

Na e-Nabavkama se ne prikupljaju javni pozivi za usluge iz Aneksa II, direktni sporazumi i poništeni postupci.

## Kad nešto ne radi

Dugme „Izvori“ na stranici pokazuje stanje svakog izvora. Kad izvor zakaže, stranica zadržava njegove zadnje uspješno preuzete objave i ispisuje grešku. Stranice izvora se povremeno mijenjaju, pa kolektor tada treba popraviti: tekst greške iz prozora „Izvori“ je dovoljan za dijagnozu.

Ako podaci nisu osvježeni duže od jednog dana, otvori karticu Actions. GitHub zna pauzirati zakazane zadatke u repozitoriju koji dugo nema aktivnosti. Tada na vrhu kartice stoji dugme za ponovno uključivanje.

## Postavke

Fajl `config.json` određuje šta se prikuplja. U dijelu `ted` su države za koje se s TED-a uzimaju sve objave i nazivi agencija čije se usluge prate. U dijelu `excluded` su izvori koji su namjerno izostavljeni i razlog. Izmjena važi od sljedećeg osvježavanja.

Izvor se isključuje brisanjem njegovog naziva iz liste `MODULES` na vrhu fajla `collect.py`.

## Napomena o korištenju podataka

Stranica je javna za svakoga ko ima link, ali je označena tako da je pretraživači ne indeksiraju. Prikazuje samo naziv, naručioca, datume i link na originalnu objavu. Platforma PLACE (izvor za Expertise France) i sajtovi ebrd.com i undp.org u uslovima korištenja imaju opće klauzule koje ograničavaju preuzimanje sadržaja. Ako to želiš izbjeći, isključi te izvore.

## Tehnički

`collect.py` pokreće kolektore iz foldera `collectors` i piše `data/tenders.json` i `data/status.json`. `index.html` je cijela stranica. `.github/workflows/daily.yml` je dnevni raspored. Pravila za pisanje novog kolektora su u `collectors/CONTRACT.md`.

Lokalno pokretanje: `pip install -r requirements.txt`, zatim `python collect.py`. Samo jedan izvor: `python collect.py --only TED`.
