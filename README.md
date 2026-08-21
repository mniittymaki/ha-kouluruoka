# Home Assistant – Kouluruoka (Haagan yläkoulu)

Hakee näillä konfifuraatiolla Haagan yläkoulun (Vanha Viertotie)** -ruokalistan [kouluruoka.fi](https://kouluruoka.fi/)-palvelusta ja tuo sen Home Assistantiin.
Paketti on tehty Haagan yläkoululle, mutta sama tapa toimii **millä tahansa** kouluruoka.fi:ssä olevalla koululla.

- Sensorit: tämän päivän + huomisen **lounas** (ei kasvislounasta)
- Automaatio: lisää viikon lounaat Local Calendariin
- Data: `https://kouluruoka.fi/page-data/menu/helsinki_haaganylakouluvanhaviertotie/page-data.json`

## Asennus

### 1. Local Calendar
1. **Asetukset → Laitteet ja palvelut → Lisää integraatio → Local Calendar**
2. Nimeksi esim. `Kouluruoka`  
   → entity_id: `calendar.kouluruoka`

### 2. Package
1. Luo kansio `config/packages/` (jos ei ole)
2. Kopioi `kouluruoka.yaml` sinne
3. Varmista `configuration.yaml`:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

4. **Tarkista konfiguraatio** → käynnistä Home Assistant uudelleen

### 3. Automaatio
Kopioi `automation_example.yaml` -sisältö UI:n automaatioeditoriin (YAML-moodi)  
tai lisää `automations.yaml`-tiedostoon.

Automaatio:
- ajaa klo **06:30** joka aamu
- ajaa myös HA:n käynnistyessä
- luo all-day-tapahtumat Local Calendariin

### Sensorit

| Entity | Kuvaus |
|--------|--------|
| `sensor.kouluruoka_raaka` | Raakadata (Days-attribuutti) |
| `sensor.kouluruoka_tanaan` | Tämän päivän lounas |
| `sensor.kouluruoka_huomenna` | Huomisen lounas |

## Lovelace-korttiesimerkit

### Yksinkertainen entities-kortti

```yaml
type: entities
title: Kouluruoka
show_header_toggle: false
entities:
  - entity: sensor.kouluruoka_tanaan
    name: Tänään
    icon: mdi:food
  - entity: sensor.kouluruoka_huomenna
    name: Huomenna
    icon: mdi:food-outline
```

### Mushroom-kortit (suositus)

```yaml
type: vertical-stack
cards:
  - type: custom:mushroom-title-card
    title: Kouluruoka
    subtitle: Haagan yläkoulu
  - type: custom:mushroom-template-card
    primary: Tänään
    secondary: "{{ states('sensor.kouluruoka_tanaan') }}"
    icon: mdi:food
    icon_color: green
    multiline_secondary: true
  - type: custom:mushroom-template-card
    primary: Huomenna
    secondary: "{{ states('sensor.kouluruoka_huomenna') }}"
    icon: mdi:food-outline
    icon_color: blue
    multiline_secondary: true
```

### Markdown + template (ilman custom-kortteja)

```yaml
type: markdown
content: |
  ## 🍽️ Kouluruoka
  **Tänään:** {{ states('sensor.kouluruoka_tanaan') }}
  
  **Huomenna:** {{ states('sensor.kouluruoka_huomenna') }}
```

### Kalenterikortti

```yaml
type: calendar
entities:
  - calendar.kouluruoka
initial_view: listWeek
```

## Muiden koulujen ruokalistat

Paketti on tehty Haagan yläkoululle, mutta sama tapa toimii **millä tahansa** kouluruoka.fi:ssä olevalla koululla.

### 1. Etsi koulu
1. Avaa [kouluruoka.fi](https://kouluruoka.fi/)
2. Hae koulun tai kaupungin nimellä
3. Avaa koulun ruokalistasivu

Esimerkki:
```
https://kouluruoka.fi/menu/helsinki_haaganylakouluvanhaviertotie/
```

### 2. Ota slug talteen
URL:n loppuosa on **slug**:

| Koko URL | Slug |
|----------|------|
| `.../menu/helsinki_haaganylakouluvanhaviertotie/` | `helsinki_haaganylakouluvanhaviertotie` |
| `.../menu/porvoo_koulut/` | `porvoo_koulut` |
| `.../menu/turku_puolalankoulukauppiaskadunyksikko/` | `turku_puolalankoulukauppiaskadunyksikko` |

### 3. Vaihda data-osoite
JSON-data löytyy aina osoitteesta:

```
https://kouluruoka.fi/page-data/menu/{SLUG}/page-data.json
```

Muuta `packages/kouluruoka.yaml`-tiedostossa `resource`-rivi:

```yaml
rest:
  - resource: "https://kouluruoka.fi/page-data/menu/TÄHÄN_SLUG/page-data.json"
```

Esim. Porvoon koulut:
```yaml
resource: "https://kouluruoka.fi/page-data/menu/porvoo_koulut/page-data.json"
```

### 4. (Valinnainen) Nimet ja unique_id
Jos käytät useaa koulua samaan aikaan, vaihda myös:
- `name:` (esim. `Kouluruoka Porvoo Raaka`)
- `unique_id:` (esim. `kouluruoka_porvoo_raaka`)
- template-sensorien nimet ja entity-viittaukset
- automaation `calendar.create_event` -kohde ja muuttujat

Muuten entityt menevät päällekkäin.

### 5. Lounas vs. kasvislounas
Oletuksena poimitaan vain `MealType == 'Lounas'`.

Jos haluat kasvislounaan:
- vaihda ehto `'Kasvislounas'`
- tai tee erilliset sensorit molemmille

### 6. Testaa
1. Tallenna → tarkista konfiguraatio → käynnistä HA (tai odota REST-päivitystä)
2. Tarkista `sensor.kouluruoka_raaka` → attribute `Days`
3. Jos `Days` on tyhjä, slug on väärä tai koulu ei ole listalla

### Vinkki
Voit kopioida koko `kouluruoka.yaml`-tiedoston useaksi paketiksi:
- `kouluruoka_haaga.yaml`
- `kouluruoka_porvoo.yaml`

ja vaihtaa kuhunkin oman slug + unique_id -arvot.

## Huomioita

- Näyttää vain **Lounas**-vaihtoehdon (ei Kasvislounasta)
- Päivämäärä parsitaan muodosta `"torstai 20.8."`
- Jos koulu vaihtuu, vaihda `resource`-URL ja slug `kouluruoka.yaml`:ssä

## Lähde

Data: [kouluruoka.fi](https://kouluruoka.fi/menu/helsinki_haaganylakouluvanhaviertotie/)
