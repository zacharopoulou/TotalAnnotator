# MedCAT with TotalAnnotator (local Docker)

How to run **CogStack MedCATservice** on your own machine with **Docker**, then point **TotalAnnotator** at it. 

For the upstream project and API details, see [CogStack/MedCATservice](https://github.com/CogStack/MedCATservice).



git clone https://github.com/CogStack/MedCATservice.git





download the example MedMen model




```bat
cd path\to\MedCATservice\scripts

set MODEL_NAME=medmen
set MODEL_VOCAB_URL=https://cogstack-medcat-example-models.s3.eu-west-2.amazonaws.com/medcat-example-models/vocab.dat
set MODEL_CDB_URL=https://cogstack-medcat-example-models.s3.eu-west-2.amazonaws.com/medcat-example-models/cdb-medmen-v1.dat
set MODEL_META_URL=https://cogstack-medcat-example-models.s3.eu-west-2.amazonaws.com/medcat-example-models/mc_status.zip

py -3 -m pip install requests
py -3 download_model.py
```

or

```powershell
cd path\to\MedCATservice\scripts

$env:MODEL_NAME = "medmen"
$env:MODEL_VOCAB_URL = "https://cogstack-medcat-example-models.s3.eu-west-2.amazonaws.com/medcat-example-models/vocab.dat"
$env:MODEL_CDB_URL = "https://cogstack-medcat-example-models.s3.eu-west-2.amazonaws.com/medcat-example-models/cdb-medmen-v1.dat"
$env:MODEL_META_URL = "https://cogstack-medcat-example-models.s3.eu-west-2.amazonaws.com/medcat-example-models/mc_status.zip"

py -3 -m pip install requests
py -3 .\download_model.py
```

You should see files under **`MedCATservice\models\medmen\`** when this finishes.

---

## 4. Start MedCAT with Docker

```bat
cd path\to\MedCATservice\docker
docker compose up -d
```

The default **compose** file maps the service to **port 5555** on your PC (container internal port remains 5000).

**Check that it is alive — `GET /api/info`**

Open in a browser (or any HTTP client):

`http://127.0.0.1:5555/api/info`

You should see JSON similar to this 

```json
{
  "service_app_name": "MedCAT",
  "service_language": "en",
  "service_version": "2.4.0.dev0",
  "service_model": "MedMen",
  "model_card_info": {
    "ontologies": "None",
    "meta_cat_model_names": ["Status"],
    "rel_cat_model_names": [],
    "model_last_modified_on": "2026-05-01T20:17:57.635522"
  }
}
```

That confirms the Flask app is up and the **MedMen** model pack is loaded.

**Note:** `/api/process` expects **POST** with JSON. Opening `/api/process` in a browser (GET) may show `{"detail":"Method Not Allowed"}` — that is normal.

**Leave Docker Desktop running** while you annotate. After a reboot, start Docker again and, if needed, run `docker compose up -d` again from the `docker` folder.

Configure TotalAnnotator



   ```env
   MEDCAT_API_URL=http://127.0.0.1:5555/api/process
   ```

The helper script **`scripts\fetch.cmd`** loads `.env` automatically before running Python.

---

## 6. Run a fetch with MedCAT

From the TotalAnnotator root, using **cmd**:

```bat
scripts\fetch_pmids.cmd 36403686 --annotator medcat
```



### for the full MedCAT HTTP JSON

Large output — use when you need **`type_ids`**, **`meta_anns`**, and the rest of the raw service payload:

```bat
scripts\fetch_pmids.cmd 36403686 --annotator medcat --medcat-raw
```

That adds **`medcat_raw`** next to **`medcat`** for each document. You can also enable this via TOML: **`[annotators.medcat] include_raw = true`** in a config passed to `fetch_pmids.py` (see `configs/examples/fetch-script.toml`).

