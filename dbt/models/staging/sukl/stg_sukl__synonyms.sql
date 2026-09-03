with source as (
    select *
    from {{ source('bronze', 'sukl_synonyms') }}
    where _batch_id = (select max(_batch_id) from {{ source('bronze', 'sukl_synonyms') }})
)

select
    "KOD_LATKY"              as ingredient_code,
    "SQ"                     as sequence,
    "ZDROJ"                  as alias_source,
    trim("NAZEV")            as alias_name,
    lower(trim("NAZEV"))     as alias_normalized,
    _batch_id,
    _source_file,
    _load_ts
from source
where "KOD_LATKY" is not null
    and "NAZEV" is not null
    and trim("NAZEV") != ''
