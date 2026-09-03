-- Active ingredients only (S = 'L'). Excipients (S = 'X') excluded here.
-- AMNT cast to numeric where possible; 'PL' (qs — quantum satis) → null with flag.

with source as (
    select *
    from {{ source('bronze', 'sukl_contains') }}
    where _batch_id = (select max(_batch_id) from {{ source('bronze', 'sukl_contains') }})
),

active_only as (
    select
        "KOD_SUKL"                                       as registration_code,
        "KOD_LATKY"                                      as ingredient_code,
        "SQ"                                             as sequence,
        "S"                                              as ingredient_type,
        "AMNT"                                           as dose_amount_raw,
        trim("UN")                                       as dose_unit,
        case
            when "AMNT" ~ '^[0-9]+(\.[0-9]+)?$'
                then "AMNT"::numeric
            else null
        end                                              as dose_amount,
        "AMNT" = 'PL'                                    as is_quantity_sufficient,
        _batch_id,
        _source_file,
        _load_ts
    from source
    where "S" = 'L'
        and "KOD_SUKL" is not null
        and "KOD_LATKY" is not null
)

select * from active_only
