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

Folder `data` se nikad ne prenosi ručno. U njemu alat čuva podatke i evidenciju o tome kad je koju objavu prvi put vidio. Ni `experts.enc.json`, `reference.enc.json` i folderi `cv` i `refdocs` ne mijenjaju se ručno: njih piše stranica (tabovi Eksperti i Reference). Zato dnevno osvježavanje prije spremanja podataka povuče izmjene koje je u međuvremenu spremila stranica (`git pull --rebase` u fajlu `.github/workflows/daily.yml`).

## Korištenje

U sredini zaglavlja su tri taba: OBJAVE (tenderi i javni pozivi), EKSPERTI i REFERENCE. Eksperti i reference su šifrirani istom šifrom kao interni izvori; dok nije otključano, tab ima katanac i dugme „Otključaj“. Adresa pamti tab (npr. `#reference`), pa osvježavanje stranice i dugme Nazad ostaju na istom mjestu.

Filteri su lijevo: moje oznake, ključne riječi, AI ocjena, sektor, vrsta ugovora, izvor, vrsta naručioca, država, regija u BiH, faza, ko može ponuditi, oblast po CPV kodu, rok i procijenjena vrijednost. Broj uz svaku opciju pokazuje koliko objava ona daje uz ostale izabrane filtere. Filteri s mnogo opcija (država, izvor, oblast, regija, vrsta naručioca) imaju polje za brzu pretragu: upiši npr. „njem“ za Njemačku ili „BiH“; Esc briše upisano. Dugme „Očisti sve filtere“ na vrhu menija vraća prikaz svih objava. Dugme „Objavljeno danas“ iznad liste pokazuje objave koje su se pojavile u današnjem osvježavanju; broj na dugmetu kaže koliko ih je, a te objave su u listi na svijetloplavoj podlozi. Objava objavljena prije više od sedmice koju alat tek sada vidi (npr. nova država ili novi izvor) ne računa se kao današnja. Opcije u filterima su poredane po abecedi; e-Nabavke BiH i Bosna i Hercegovina su uvijek prve, a „Ostalo“ zadnje. Na mobitelu i tabletu filteri se otvaraju dugmetom „Filteri“ pored pretrage; broj u zagradi kaže koliko je filtera uključeno.

Ključne riječi se odvajaju zarezom i dovoljan je korijen riječi („energetsk“ nalazi i „energetska“ i „energetske“). Kvačice nisu bitne. Nazivi na ćirilici prikazuju se latinicom (preslovljeno, nije prevod), a izvorni naziv se vidi kad se mišem stane na naziv. Kvačica „traži i istoznačnice na drugim jezicima“ (uključena sama od sebe) dodaje istu riječ na drugim jezicima: „okoliš“ nalazi i „environment“, „Umwelt“ i „životna sredina“. Ispod polja piše šta je dodano.

Uz svaku objavu su dugmad „Pratim“ i „Sakrij“. Praćene i sakrivene objave biraju se pod „Moje oznake“; sakrivene se više ne prikazuju dok ih ne vratiš. Stranica pamti i koje si podatke zadnji put vidio, pa iznad liste piše koliko je objava novih od zadnje posjete. Oznake, zadnja posjeta i profili čuvaju se u pregledniku u kojem su napravljeni i ne dijele se s kolegama. Za drugi uređaj koristi izvoz i uvoz u prozoru „Sačuvaj profil“; „Kopiraj link“ prenosi samo filtere.

Dugme „Pošalji“ uz objavu priprema poruku s naslovom, ključnim podacima i linkom na objavu. Primaoca upišeš u prozoru ili tek u samoj poruci. Stranica sama ne šalje ništa; poruku šalješ ti. „Otvori u Outlooku“ preuzme gotovu poruku s tabelom (.eml fajl): klikni preuzeti fajl i Outlook je otvori spremnu za slanje. „Otvori e-mail“ i „Otvori u Gmailu“ otvaraju poruku s podacima kao tekstom, jer link koji otvara poruku ne može prenijeti tabelu; tabela se pri tome kopira sama, pa je u poruci zalijepiš sa Ctrl+V preko redova s podacima. Stranica pamti način koji si zadnji put koristio. „Kopiraj tabelu“ kopira tabelu za Word ili chat. Adrese koje upišeš pamte se samo u tom pregledniku. Tabela ima i red „Preostalo dana“ do roka, računato od današnjeg dana: do 3 dana crveno, do 7 narandžasto, više zeleno.

Više objava jednim e-mailom: označi kvadratiće lijevo od roka i na dnu ekrana klikni „Pošalji označeno“. Poruka ima jednu tabelu s redom po objavi (naziv kao link, naručilac, rok, preostalo dana u boji, država, izvor), poredanu po roku. „Označi prikazane“ označi sve objave u listi, a „Poništi“ briše izbor.

Kalendar: dugme „Kalendar“ uz objavu otvara novi događaj u Outlooku na webu, s nazivom, rokom, naručiocem i linkom na objavu; provjeriš ga, izabereš podsjetnik i klikneš Save (podsjetnik se ne može zadati linkom). Rok bez sata je cjelodnevni događaj, a kod najave se upisuje očekivani datum poziva. Zadano je poslovni Outlook (Microsoft 365); „Drugi kalendar“ u poruci nakon klika nudi Outlook.com i .ics fajl, a izbor se pamti u pregledniku. „U kalendar“ za označene objave otvara listu rokova s dugmetom „Dodaj“ uz svaki. Na računaru ovo radi u pregledniku; na mobitelu se Outlook otvara u pregledniku, ne u aplikaciji.

Najave: filter „Faza“ dijeli objave na otvorene (imaju rok) i najave, odnosno prethodna obavještenja o nabavkama koje tek dolaze (TED, Svjetska banka za Zapadni Balkan, najavljeni pozivi EU programa). Najava u koloni roka pokazuje kad se očekuje poziv, ako je naručilac to naveo, i ostaje u listi do 30 dana poslije tog datuma, odnosno 120 dana od objave.

Kad neki izvor ne radi ili podaci nisu osvježeni duže od 36 sati, na dugmetu „Izvori“ je crvena oznaka (npr. „1 ne radi“), a iznad liste poruka s nazivom izvora.

Sektor (energija, okoliš, ostalo) i „ko može ponuditi“ (organizacija, pojedinac, ostalo, nepoznato) alat određuje sam, pa su približni. Sektor ide po CPV kodu gdje ga izvor daje i po riječima u nazivu. Nabavke naftnih derivata (gorivo, lož ulje, maziva) ne računaju se u energiju, a nabavke uglja, peleta, plina, električne i toplotne energije se računaju. Ko može ponuditi uzima se iz izvora kad ga on navodi (Svjetska banka), javne nabavke (e-Nabavke, TED, EU) vode se kao pozivi za organizacije, a kod ostalih odlučuju riječi u nazivu, na primjer „individual consultant“ ili oznaka postupka RFP. „Ostalo“ su pozivi otvoreni i firmama i pojedincima te pozivi za nevladine organizacije. Pravila za oboje su u fajlu `index.html`.

Filter po procijenjenoj vrijednosti radi u KM. Iznosi u drugim valutama preračunavaju se po dnevnoj kursnoj listi ECB-a, a 1 EUR je 1,95583 KM. Vrijednost objavljuju e-Nabavke, Svjetska banka i dio objava TED-a i EU portala.

Oznaka „rok pomjeren“ pojavi se kad se rok objave promijeni između dva osvježavanja. Na TED-u je ispravka nova objava s novim brojem, pa se tamo pomjeren rok vidi kao nova objava.

Oznaka „novo“ stoji uz objave koje su stigle poslije tvoje zadnje posjete. Pri prvoj posjeti stoji uz objave koje je alat prvi put vidio danas ili jučer.

## Javni pozivi (grantovi)

Prekidač „Tenderi / Javni pozivi“ iznad liste dijeli objave na nabavke (posao za firmu) i javne pozive za grantove i sredstva. Svaki dio pamti svoje filtere. Javne pozive daju EU programi (Horizon Europe, LIFE, Erasmus+ i drugi), UNDP-ovi pozivi za prijedloge, CzechAid, Fond za zaštitu okoliša FBiH, Eko fond RS, FMRPO, i Mreža mira.

AI javne pozive ocjenjuje za CETEOR i za REIC: ocjena od 0 do 3, za koga je poziv (filter „AI: za koga je poziv“) i kratko obrazloženje s tim ko smije aplicirati. Opis REIC-a i pravila za pozive su u fajlu `ai_okvir.md`. Ko smije aplicirati AI procjenjuje iz naziva poziva, pa uslove uvijek provjeri u samom pozivu.

## DevelopmentAid (isključen)

DevelopmentAid je isključen: pretraga tendera i grantova preko API-ja se plaća dodatno uz članarinu, a uslovi stranice i zaštita od robota ne dozvoljavaju automatsko preuzimanje sa stranice. Kod ostaje u fajlu `collectors/developmentaid.py`. Ako se pretraga jednom plati, izvor se uključuje dodavanjem `"developmentaid"` u listu `MODULES` u `collect.py` i brisanjem unosa `DA` iz liste `excluded` u `config.json`; ključ ide u GitHub secret `DA_API_KEY`.

## AI: ocjena za CETEOR i Pitaj AI

Ocjena za CETEOR: pri svakom osvježavanju AI pročita nove objave i svakoj da ocjenu od 0 do 3 (3 jako relevantno, 2 moguće, 1 slabo, 0 nije za nas) i jednu rečenicu obrazloženja. Na stranici su filter „AI ocjena za CETEOR“, poredak „AI ocjena, najbolje prvo“ i oznaka „AI 3/3“ uz objavu. AI ocjenjuje po okviru iz fajla `ai_okvir.md`: opis CETEOR-a i REIC-a, pravila za ocjene 0 do 3 (vrste posla, geografija, naručioci, individualni eksperti, vrijednost ugovora, javni pozivi) i primjeri iz referenci. Uz svaku objavu AI vidi naziv, engleski prijevod ako ga ima, naručioca, državu, vrstu ugovora i postupka, CPV kod, vrijednost i izvor, ali ne i projektni zadatak. Svaka objava se ocjenjuje jednom. Okvir se mijenja na GitHubu olovkom; svaka izmjena teksta pokreće ponovno ocjenjivanje svih objava, postepeno: prvo se ocjenjuju nove objave, pa stare po novom okviru (najviše 12 minuta po osvježavanju, ostatak sljedeći dan; ukupno oko 1,5 USD). Do tada uz staru objavu ostaje stara ocjena, a u prozoru „Izvori“ piše koliko ih još čeka. Tekst između `<!--` i `-->` je napomena za ljude i AI ga ne vidi. Ocjenjuju se i objave internih izvora (GIZ, OSCE); ocjene ostaju u šifriranom fajlu zajedno s objavama. Ako to ne želiš, u `config.json` postavi `"include_private": false`.

Pitaj AI: dugme pored pretrage. Napišeš običnim jezikom šta tražiš, a AI postavi filtere u prikazu u kojem si (tenderi ili javni pozivi); „Vrati prethodne“ u poruci vraća stare. Prvi put stranica traži API ključ i pamti ga samo u tom pregledniku.

Postavljanje (jednom):

1. Na console.anthropic.com napravi račun. U dijelu Billing uplati kredit (npr. 5 USD) i postavi mjesečni limit potrošnje.
2. Pod API keys klikni Create key i kopiraj ključ.
3. Na GitHubu otvori Settings, zatim Secrets and variables, zatim Actions i klikni New repository secret. Name: `ANTHROPIC_API_KEY`, Secret: ključ. Klikni Add secret.
4. U fajlu `.github/workflows/daily.yml` (olovka) ispod reda s `TR_PASSPHRASE` mora stajati red `ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}`, uvučen isto kao red iznad.
5. Za Pitaj AI isti ključ (ili poseban) upiši na stranici kad je zatraži.

AI prijevod: naslovi koji nisu na bosanskom, hrvatskom, srpskom, crnogorskom ili engleskom (npr. švedski, češki, francuski) dobiju kratak prijevod na engleski. Prijevod je ispod originalnog naslova, ljubičastom bojom i s oznakom EN; pretraga ga uzima u obzir, a ima ga i u CSV-u i u poruci „Pošalji“. Svaki naslov se provjerava jednom. Prevode se i interni izvori (npr. GIZ-ovi naslovi na njemačkom). Prijevod se isključuje s `"translate": false` u dijelu `ai` u `config.json`.

AI sažetak: za objave s ocjenom 2 ili 3, kad izvor daje opis posla (TED, e-Nabavke, EU Funding & Tenders, Svjetska banka), AI napiše sažetak do 45 riječi: šta se traži, ko smije ponuditi ili aplicirati, budžet, trajanje i ključni eksperti, ako su navedeni. Ispod objave stoji „Sažetak (AI)“; klik ga otvara. Sažetak je i u CSV-u, u poruci „Pošalji“ i u pretrazi. Pravi se do 300 sažetaka po osvježavanju, prvo za ocjenu 3. Isključuje se s `"summary": false` u dijelu `ai` u `config.json`.

Cijena: model je Claude Haiku 4.5 (1 USD na milion ulaznih i 5 USD na milion izlaznih tokena). Prvo ocjenjivanje svih objava košta oko 1 USD, prva provjera naslova za prijevod manje od 0,50 USD, a prvi sažeci oko 1 USD; poslije toga sve zajedno košta nekoliko centi dnevno. Jedno pitanje u Pitaj AI košta manje od jednog centa. Bez ključa sve ostalo radi kao i prije.

## Dobitnici ugovora

Dugme „Dobitnici“ u zaglavlju pokazuje ko je u zadnjih 12 mjeseci dobio ugovore za usluge i po kojoj cijeni:

- e-Nabavke BiH: dodijeljeni ugovori iz kategorija istraživanje i razvoj, istraživanje tržišta, konsalting u menadžmentu te arhitektonske, inženjerske i naučno-tehničke konsultantske usluge; iz kategorije „Ostale usluge“ samo ugovori čiji naziv govori o okolišu, energiji, emisijama, otpadu, buci, zraku ili studijama. Direktni sporazumi (mali ugovori bez nadmetanja) se ne uzimaju.
- TED: dodjele ugovora za usluge u državama Zapadnog Balkana i Hrvatskoj, s CPV kodom 71 (arhitektonske i inženjerske usluge), 73 (istraživanje i razvoj), 793 i 794 (istraživanje tržišta i konsalting) i 907 (okolišne usluge).

Kartica „Najčešći dobitnici“ broji ugovore po firmi, s ukupnom vrijednošću i prosječnim brojem ponuda; klik na firmu pokazuje njene ugovore. Kod konzorcija se ugovor i njegova puna vrijednost računaju svakom članu. Kartica „Ugovori“ ima datum, naziv s linkom na objavu, naručioca, dobitnika, vrijednost i broj ponuda; na e-Nabavkama i raspon prihvatljivih ponuda kad je objavljen. Pretraga, država i period sužavaju obje kartice, a „Preuzmi CSV“ preuzima prikazane ugovore.

Uz objavu čiji je naručilac u zadnjih 12 mjeseci dodijelio neki od tih ugovora stoji „Ranije dodjele naručioca (broj)“: klik pokazuje te ugovore. Naručilac se prepoznaje po nazivu, pa se objave i dodjele na TED-u i e-Nabavkama povezuju samo kad naziv glasi isto.

Prvo preuzimanje traje oko dvije minute; poslije toga se svaki dan preuzimaju samo nove i izmijenjene dodjele. Kategorije, riječi i CPV kodovi su u dijelu `awards` u `config.json`; s `"ejn_direct": true` uzimaju se i direktni sporazumi.

## Slične reference

Uz objave s AI ocjenom 2 ili 3 stoji „Slične reference (broj)“: do pet poslova iz liste referenci CETEOR-a i REIC-a koji su najsličniji objavi po nazivu, oblasti, vrsti usluge i opisu, s naručiocem i godinom. Sličnost se računa po riječima, bez AI-a, i služi kao podsjetnik koje reference navesti u ponudi.

Lista referenci je poslovna tajna, pa je na GitHubu samo šifrirana (fajl `reference.enc.json` u glavnom folderu repozitorija), istom šifrom kao interni izvori. Rezultat se također šifrira (`data/refmatch.json`), pa slične reference vidi samo ko otključa „Interni izvori“. U poruci „Pošalji“ ih nema. Klik na sličnu referencu otvara je u tabu Reference. Listu uređuješ u tabu Reference; slične reference se ponovo računaju pri sljedećem osvježavanju.

## Eksperti (roster)

Tab EKSPERTI je roster eksperata: tabela s pretragom i filterima. Stručne oblasti, tip posla, fakultet i država imaju višestruki izbor: ekspert se prikazuje ako ima bilo koju od označenih vrijednosti. Uz njih su filteri kategorija i engleski, i dugme „Očisti filtere“. Klik na naslov kolone slaže tabelu rastuće, a ponovni klik opadajuće; prazna polja su uvijek na kraju. Klik na ime otvara obrazac sa svim podacima: identifikacija i kontakt, odnos s firmom, kvalifikacije (stručna sprema i „Bez fakulteta“, engleski, maternji i ostali jezici), napomene, profil iz CV-ja i priloženi CV-jevi. Prozor se zatvara i sa X u gornjem desnom uglu. Liste stručnih oblasti i tipova posla su abecedne, s „Ostalo“ na kraju, i iste su kao u referencama. Ekspert može imati najviše 7 stručnih oblasti i najviše 4 tipa posla; stariji unos s više njih se sprema tek kad se višak odznači. Iskustvo se računa samo, od početka karijere do danas. CV se dodaje dugmetom ili prevlačenjem fajla u prozor. „Izvezi CSV“ preuzima prikazane eksperte, a „Uvezi listu“ dodaje eksperte iz JSON fajla (npr. iz Excel tabele); ekspert s istim imenom i prezimenom se ne dodaje dvaput.

Roster i CV-jevi su šifrirani istom šifrom kao interni izvori i vide se tek nakon otključavanja. Čuvaju se u repozitoriju: roster u `experts.enc.json`, a svaki CV kao `cv/<slučajni naziv>.enc`. Nazivi fajlova i opisi izmjena na GitHubu ne sadrže imena. Obrisan CV ostaje šifriran u historiji repozitorija.

Spremanje ide direktno sa stranice, preko GitHub tokena koji smije pisati samo u ovaj repozitorij. Token se postavlja jednom, u „Postavke spremanja“ (tamo su i koraci za pravljenje tokena), i čuva se samo u tom pregledniku. Bez tokena roster se može pregledati, ali ne i mijenjati. Token se povlači na GitHubu, u Settings, Developer settings, Personal access tokens.

Uvoz iz CV-ja (AI): prevučeš ili izabereš jedan ili više CV-jeva (PDF ili Word .docx), a AI iz svakog izvuče ime, kontakt, kategoriju (uposlenik ako CV pokazuje da osoba sada radi u CETEOR-u, inače vanjski saradnik), spremu, fakultet, do 7 stručnih oblasti, do 4 tipa posla, početak karijere, engleski i ostale jezike, stručni ispit, kratak profil i posebne vještine. Prijedloge pregledaš i sačuvaš označene; postojeći ekspert (isti e-mail ili ime i prezime) se samo dopunjava, a CV se prilaže. Podatke koji nisu u CV-ju (saradnja, dnevnica, poznanstvo) unosiš u obrascu. Jedan CV košta oko 2 centa; koristi se isti API ključ kao za Pitaj AI. CV se šalje Anthropicu samo radi čitanja.

Preporučeni eksperti: za tendere s AI ocjenom 2 ili 3 za CETEOR, AI pri svakom osvježavanju bira do tri eksperta iz roster-a, po stručnim oblastima, vrsti posla, iskustvu, profilu iz CV-ja, jezicima i mjestu rada; uz podjednaku stručnost prednost imaju uposlenici, pa vanjski saradnici s laganom saradnjom. Uz tender stoji „Preporučeni eksperti (broj)“ s kratkim razlogom, a klik na ime otvara eksperta. Preporuka se računa jednom po tenderu (oko 1 USD mjesečno). Kad se u roster-u promijeni nešto što AI gleda (novi ekspert, stručne oblasti, profil i slično, ali ne telefon, e-mail ili dnevnica), preporuke se postepeno računaju ponovo za sve tendere s ocjenom 2 i 3, oko 0,2 USD po takvoj izmjeni; do tada vrijede stare. Rezultat je šifriran u `data/expertmatch.json`.

## Reference

Tab REFERENCE je lista referenci CETEOR-a i REIC-a: tabela s pretragom, poretkom po kolonama i filterima s višestrukim izborom za stručnu oblast, vrstu posla, godinu (i „bez godine“), državu, naručioca (s pretragom unutar liste), vrstu naručioca i sektor, i dugme „Očisti filtere“. Stručne oblasti i vrste posla su iste liste kao kod eksperata; stara detaljna vrsta usluge (npr. „DEA - zgradarstvo“) ostaje u polju „Detaljna vrsta usluge“. Referenca može imati najviše tri stručne oblasti i tri vrste posla. Države se upisuju nazivom ili ISO kodom, više njih odvojeno zarezom; „Zapadni Balkan (regija)“ je posebna vrijednost.

Klik na naziv otvara obrazac: naziv i opis na bosanskom i engleskom, ID projekta, godina, sektor, detaljna vrsta usluge, države, naručilac i vrsta naručioca, oblasti, vrste posla i priloženi dokumenti (dugmetom ili prevlačenjem u prozor). Dokumenti se čuvaju šifrirani u folderu `refdocs`, s nazivom fajla bez naziva projekta.

„Nova iz dokumenata (AI)“: prevučeš ili izabereš dokumente jednog projekta (projektni zadatak, ugovor, izvještaj; PDF ili Word .docx), a AI popuni obrazac na oba jezika; ti ga pregledaš i sačuvaš, a dokumenti se prilože. Ako slična referenca već postoji (isti ID projekta ili naziv), obrazac na to upozori. Košta oko 5 do 20 centi po referenci, zavisno od dužine dokumenata (isti API ključ kao Pitaj AI). „Uvezi listu“ uvozi JSON listu i pita da li zamijeniti cijelu listu ili dodati samo nove reference (s nazivom i godinom koje još nema). „Izvezi CSV“ preuzima prikazane reference.

## Izvori

| Izvor | Šta se prikuplja | Način |
|---|---|---|
| e-Nabavke BiH | Sva otvorena obavještenja o nabavci (robe, usluge, radovi) | Zvanični open data API Agencije za javne nabavke |
| TED (EU) | Zapadni Balkan i Hrvatska: svi ugovori. EU institucije, međunarodne organizacije i razvojne agencije, te švedska agencija za zaštitu okoliša (Naturvårdsverket): usluge. Uz to najave (prethodna obavještenja) za iste države i institucije | Zvanični API |
| EU Funding & Tenders | Otvoreni i najavljeni tenderi EU institucija | Zvanični API |
| Svjetska banka | Svi otvoreni pozivi u svijetu; najave (opšta obavještenja o nabavkama) za Zapadni Balkan | Zvanični API |
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

Trinaest izvora nije uključeno i treba ih pregledati ručno. DevelopmentAid: pretraga preko API-ja se plaća dodatno, a stranica ne dozvoljava automatsko preuzimanje. Portal Sjeverne Makedonije (e-Nabavki) radi s drugih mreža, ali njegova zaštita od robota odbija GitHub servere. Nacionalni portali Hrvatske (EOJN RH) i Srbije (Portal javnih nabavki) u robots.txt zabranjuju automatski pristup; hrvatske nabavke iznad EU praga ipak stižu preko TED-a. Albanska agencija (APP) ima dnevni CSV izvoz, ali ga robots.txt zabranjuje robotima. Za portale Crne Gore (CEJN) i Kosova (e-Prokurimi) nije pronađen javni popis tendera koji se može čitati bez prijave. Naturvårdsverket svoje nabavke vodi na Mercellu, koji je aplikacija bez javnog popisa; njegove nabavke usluga iznad EU praga stižu preko TED-a. UNGM u uslovima korištenja zabranjuje preuzimanje sadržaja u druge sisteme bez pisane dozvole. UNOPS i FAO objavljuju preko UNGM-a i nemaju vlastitu javnu listu. EBRD-ov portal ECEPP, na kojem je većina tendera iz EBRD projekata, odbija automatski pristup, kao i sajtovi Energy Community i WWF Adria.

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

Fajl `config.json` određuje šta se prikuplja. U dijelu `ted` su države za koje se s TED-a uzimaju sve objave i nazivi agencija čije se usluge prate (oznaka `@SE` znači: samo naručilac iz te države). U listi `private_sources` su ključevi izvora koji se vode kao interni, uz one koji su to po svojoj prirodi (GIZ, OSCE). U dijelu `excluded` su izvori koji su namjerno izostavljeni i razlog. U dijelu `awards` su kategorije, riječi i CPV kodovi za dobitnike ugovora. Izmjena važi od sljedećeg osvježavanja.

Izvor se isključuje brisanjem njegovog naziva iz liste `MODULES` na vrhu fajla `collect.py`.

## Napomena o korištenju podataka

Stranica je javna za svakoga ko ima link, ali je označena tako da je pretraživači ne indeksiraju. Prikazuje samo naziv, naručioca, datume i link na originalnu objavu. Dobitnici ugovora su iz otvorenih podataka e-Nabavki i TED-a, koji su objavljeni za ponovnu upotrebu. Platforma PLACE (izvor za Expertise France) i sajtovi ebrd.com i undp.org u uslovima korištenja imaju opće klauzule koje ograničavaju preuzimanje sadržaja. Ako to želiš izbjeći, prebaci te izvore u interni dio ili ih isključi.

## Tehnički

`collect.py` pokreće kolektore iz foldera `collectors` i piše `data/tenders.json`, `data/status.json` i šifrirani `data/private.json`. `ai_score.py` je AI ocjena, AI prijevod i AI sažetak objava, a `ai_okvir.md` okvir po kojem AI ocjenjuje. `awards.py` preuzima dobitnike ugovora u `data/awards.json`, `refmatch.py` traži slične reference iz šifriranog `reference.enc.json` (piše ga tab Reference) i piše šifrirani `data/refmatch.json`, a `experts.py` iz šifriranog roster-a `experts.enc.json` bira preporučene eksperte u šifrirani `data/expertmatch.json`. Cijelo osvježavanje traje najviše 25 minuta (GitHub posao smije 30): AI koraci i dobitnici dobijaju onoliko vremena koliko je ostalo, a ostatak se radi sljedeći dan. `index.html` je cijela stranica. `.github/workflows/daily.yml` je dnevni raspored. Pravila za pisanje novog kolektora su u `collectors/CONTRACT.md`.

Lokalno pokretanje: `pip install -r requirements.txt`, zatim `python collect.py`. Samo jedan izvor: `python collect.py --only TED` (dobitnici se tada ne preuzimaju; s njima: `--only TED,AWD`). Interni izvori se lokalno preuzimaju samo ako je postavljena varijabla okruženja `TR_PASSPHRASE`.
