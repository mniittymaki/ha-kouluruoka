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
1. Hae koulu [kouluruoka.fi](https://kouluruoka.fi/)
2. Ota slug URL:sta
3. Vaihda slug `kouluruoka.yaml` (`resource`) ja `kouluruoka_e.py` (`MENU_URL`)

## Lähteet
- [kouluruoka.fi](https://kouluruoka.fi/menu/helsinki_haaganylakouluvanhaviertotie/)
- E-katalogi: [E-Number-Database](https://github.com/SuhasDissa/E-Number-Database)
- [Ruokavirasto E-koodit](https://www.ruokavirasto.fi/elintarvikkeet/ohjeita-kuluttajille/e-kooditlisaaineet/e-koodit/)
