# Home Assistant – Kouluruoka (Haagan yläkoulu)

Hakee **Haagan yläkoulu (Vanha Viertotie)** -ruokalistan [kouluruoka.fi](https://kouluruoka.fi/)-palvelusta Home Assistantiin.

## Ominaisuudet

- **Lounas** + **Kasvislounas** (tänään / huomenna)
- **Raaka-aineet** ainesosaluetteloina
- **E-koodit** poimittuna ainesosista + selitykset katalogista (562 koodia)
- **Kalenteriautomaatio** (lounas + kasvis)
- Data: kouluruoka.fi `page-data.json`

## Asennus

### 1. Local Calendar
1. **Asetukset → Laitteet ja palvelut → Lisää integraatio → Local Calendar**
2. Nimi: `Kouluruoka` → entity_id `calendar.kouluruoka`

### 2. Tiedostot

| Repo | Home Assistant |
|------|----------------|
| `kouluruoka.yaml` | `config/packages/kouluruoka.yaml` |
| `e_koodit.json` | `config/www/e_koodit.json` |
| `python_scripts/kouluruoka_e.py` | `config/python_scripts/kouluruoka_e.py` |

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Tarkista konfiguraatio → käynnistä HA uudelleen.

### 3. Automaatio
Kopioi `automation_example.yaml` UI:hin tai `automations.yaml`:ään.

## Sensorit

| Entity | Kuvaus |
|--------|--------|
| `sensor.kouluruoka_raaka` | Raakadata |
| `sensor.kouluruoka_tanaan` | Lounas tänään |
| `sensor.kouluruoka_huomenna` | Lounas huomenna |
| `sensor.kouluruoka_tanaan_kasvis` | Kasvis tänään |
| `sensor.kouluruoka_huomenna_kasvis` | Kasvis huomenna |
| `sensor.kouluruoka_tanaan_e_koodit` | E-koodit yhteensä (lounas+kasvis) |
| `sensor.kouluruoka_tanaan_e_koodit_lounas` | E-koodit vain lounas |
| `sensor.kouluruoka_tanaan_e_koodit_kasvis` | E-koodit vain kasvis |

### E-sensorin attributet
- `codes`, `details` (code/name/type/info)
- `ainesosat_lounas`, `ainesosat_kasvis`
- `lounas`, `kasvis` (objektit)

## Lovelace
Katso `lovelace_cards.yaml`.

## Muiden koulujen ruokalistat

Paketti on oletuksena Haagan yläkoululle (Vanha Viertotie), mutta sama setup toimii **millä tahansa** koululla joka löytyy [kouluruoka.fi](https://kouluruoka.fi/):stä.

### 1. Etsi koulu
1. Avaa [https://kouluruoka.fi/](https://kouluruoka.fi/)
2. Kirjoita hakukenttään koulun tai kaupungin nimi
3. Avaa oikea ruokalistasivu selaimessa

Esimerkki auki olevasta sivusta:
```
https://kouluruoka.fi/menu/helsinki_haaganylakouluvanhaviertotie/
```

### 2. Ota slug talteen
**Slug** = URL:n loppuosa `/menu/`-polun jälkeen (ilman kauttaviivaa lopussa).

| Koko osoite | Slug |
|-------------|------|
| `https://kouluruoka.fi/menu/helsinki_haaganylakouluvanhaviertotie/` | `helsinki_haaganylakouluvanhaviertotie` |
| `https://kouluruoka.fi/menu/espoo_koulut/` | `espoo_koulut` |
| `https://kouluruoka.fi/menu/turku_puolalankoulukauppiaskadunyksikko/` | `turku_puolalankoulukauppiaskadunyksikko` |

### 3. Testaa että data löytyy
Avaa selaimessa:

```
https://kouluruoka.fi/page-data/menu/SLUG/page-data.json
```

Esim. Haaga:
```
https://kouluruoka.fi/page-data/menu/helsinki_haaganylakouluvanhaviertotie/page-data.json
```

Jos näet JSON-tekstiä (ei 404-sivua), slug on oikein.

### 4. Vaihda slug kahteen tiedostoon

**A) `config/packages/kouluruoka.yaml`**

Etsi rivi:
```yaml
resource: "https://kouluruoka.fi/page-data/menu/helsinki_haaganylakouluvanhaviertotie/page-data.json"
```

Vaihda keskiosa (`helsinki_...`) uudeksi slugiksi:
```yaml
resource: "https://kouluruoka.fi/page-data/menu/UUSI_SLUG/page-data.json"
```

**B) `config/python_scripts/kouluruoka_e.py`**

Etsi rivit:
```python
MENU_URL = (
    "https://kouluruoka.fi/page-data/menu/"
    "helsinki_haaganylakouluvanhaviertotie/page-data.json"
)
```

Vaihda samaksi slugiksi:
```python
MENU_URL = (
    "https://kouluruoka.fi/page-data/menu/"
    "UUSI_SLUG/page-data.json"
)
```

### 5. Käynnistä uudelleen
1. Tallenna molemmat tiedostot
2. **Tarkista konfiguraatio**
3. Käynnistä Home Assistant uudelleen (tai ainakin `command_line` + template -entityt)

### 6. Varmista että toimii
- `sensor.kouluruoka_raaka` → attribute `Days` ei ole tyhjä
- `sensor.kouluruoka_tanaan` näyttää ruoan nimen
- Jos `Days` on tyhjä → slug väärä tai koulu ei ole listalla tällä viikolla

### Useita kouluja samaan aikaan
Jos haluat esim. Haagan **ja** toisen koulun:
1. Kopioi `kouluruoka.yaml` → `kouluruoka_toinen.yaml`
2. Kopioi `kouluruoka_e.py` → `kouluruoka_toinen_e.py`
3. Vaihda **jokaiseen** entityyn uniikit nimet ja `unique_id`:t  
   (esim. `sensor.kouluruoka_haaga_tanaan`, `sensor.kouluruoka_espoo_tanaan`)
4. Osoita toisen skriptin `MENU_URL` toiseen slugiin
5. Muuten entityt menevät päällekkäin

## Lähteet
- [kouluruoka.fi](https://kouluruoka.fi/menu/helsinki_haaganylakouluvanhaviertotie/)
- E-katalogi: [E-Number-Database](https://github.com/SuhasDissa/E-Number-Database)
- [Ruokavirasto E-koodit](https://www.ruokavirasto.fi/elintarvikkeet/ohjeita-kuluttajille/e-kooditlisaaineet/e-koodit/)
