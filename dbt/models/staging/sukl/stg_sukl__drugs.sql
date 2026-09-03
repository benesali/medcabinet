with source as (
    select *
    from {{ source('bronze', 'sukl_drugs') }}
    where _batch_id = (select max(_batch_id) from {{ source('bronze', 'sukl_drugs') }})
),

renamed as (
    select
        "KOD_SUKL"                                        as registration_code,
        trim("NAZEV")                                     as name,
        trim("FORMA")                                     as dosage_form,
        trim("SILA")                                      as strength,
        trim("BALENI")                                    as packaging,
        trim("CESTA")                                     as route,
        trim("ATC_WHO")                                   as atc_code,
        "REG"                                             as reg_status,
        case when "REG" = 'R' then 'active' else 'withdrawn' end as status,
        trim("RC")                                        as registration_number,
        "VYDEJ"                                           as dispensing_class,
        trim("DRZITEL")                                   as authorisation_holder,
        trim("VYROBCE")                                   as manufacturer,
        "LL"                                              as ingredient_codes_raw,
        _batch_id,
        _source_file,
        _load_ts
    from source
    where "KOD_SUKL" is not null
        and trim("KOD_SUKL") != ''
)

select * from renamed
