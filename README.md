# Home Assistant · Kouluruoka

Hakee koulun ruokalistan [kouluruoka.fi](https://kouluruoka.fi/)-palvelusta Home Assistantiin.

Oletuskoulu on **Haagan yläkoulu (Vanha Viertotie)**, mutta mikä tahansa kouluruoka.fi-koulu käy. Ei kytköstä kouluruoka.fi:hin.

## Ominaisuudet

- Lounas + kasvislounas (tänään / huomenna)
- Raaka-aineet
- E-koodit + katalogi (562 koodia)
- E-koodihistoria (top-lista, 365 pv)
- Ravintoarvio (kcal, P/H/R, suola)
- Huomiot: `ok` / `epailyttava` / `huomio` / `varoitus`
- Kalenteri (lounas + kasvis)

## Asennus

### HACS (suositus)

1. HACS → kolmen pisteen valikko → Custom repositories
2. URL: `https://github.com/mniittymaki/ha-kouluruoka`
3. Tyyppi: **Integration**
4. Asenna **Kouluruoka**
5. Käynnistä Home Assistant
6. Asetukset → Laitteet ja palvelut → Lisää integraatio → **Kouluruoka**

### Manuaalisesti (Docker / Container)

1. Kopioi `custom_components/kouluruoka` → `/config/custom_components/kouluruoka`
2. Käynnistä Home Assistant
3. Lisää integraatio **Kouluruoka**

## Asetukset

| Kenttä | Selite |
|---|---|
| Slug | kouluruoka.fi-URL:n `/menu/`-osa, esim. `helsinki_haaganylakouluvanhaviertotie`. Voit liittää myös koko menu-osoitteen. |
| Nimi | Valinnainen laitteen nimi HA:ssa |
| Päivitysväli | Oletus 21600 s (6 h) |

### Slug

1. Avaa [kouluruoka.fi](https://kouluruoka.fi/)
2. Etsi koulu ja avaa ruokalista
3. Ota URL:n loppuosa:

`https://kouluruoka.fi/menu/helsinki_haaganylakouluvanhaviertotie/`
→ `helsinki_haaganylakouluvanhaviertotie`

Testaa: `https://kouluruoka.fi/page-data/menu/SLUG/page-data.json` ei saa olla 404.

Useita kouluja: lisää integraatio uudestaan toisella slugilla.

## Entiteetit

Laite-nimen etuliite riippuu config flow -nimestä. Jos nimi on `Kouluruoka`:

| Entity | Kuvaus |
|---|---|
| `sensor.kouluruoka_lounas_tanaan` | Lounas tänään |
| `sensor.kouluruoka_kasvis_tanaan` | Kasvis tänään |
| `sensor.kouluruoka_lounas_huomenna` | Lounas huomenna |
| `sensor.kouluruoka_kasvis_huomenna` | Kasvis huomenna |
| `sensor.kouluruoka_e_koodit` | E-koodit tänään |
| `sensor.kouluruoka_e_koodit_historia` | Eri koodeja historiassa |
| `sensor.kouluruoka_e_koodit_yleisin` | Yleisin E-koodi |
| `sensor.kouluruoka_ravinto_lounas` | kcal-arvio |
| `sensor.kouluruoka_huomio_lounas` | ok / epailyttava / huomio / varoitus |
| `calendar.kouluruoka_kalenteri` | Viikon ruoat |

Lovelace-esimerkki: `examples/lovelace_cards.yaml` (päivitä entity-id:t laitteen nimen mukaan).

## Huomiot

Sääntöpohjainen tarkistus, ei lääketieteellinen arvio.

- **varoitus**: voimakassuolainen, MSM/kamara, palmuöljy, nitriitit, korkea suola
- **huomio**: siirapit, proteiinivalmiste, makeutusaineet, korkea sokeri
- **epailyttava**: aromit, emulgaattorit, muunnettu tärkkelys, E466/E471 yms.

Ravintoarvot kouluruoka.fi:ssä ovat **per 100 g**. Integraatio skaalaa ne VRN-koululaisannoksilla.

## Vanha YAML-paketti

Aiempi `packages/`-asennus on esimerkissä `examples/kouluruoka_package.yaml`. HACS-integraatio korvaa sen: poista vanha paketti ja python_scripts-ajo, ettei tule tuplasensoreita.

## Lähteet

- [kouluruoka.fi](https://kouluruoka.fi/)
- E-katalogi: [E-Number-Database](https://github.com/SuhasDissa/E-Number-Database)
- [Ruokavirasto E-koodit](https://www.ruokavirasto.fi/elintarvikkeet/ohjeita-kuluttajille/e-kooditlisaaineet/e-koodit/)

## License

MIT
