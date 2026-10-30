with source as (

    select * from {{ source('frankfurter', 'rates') }}

),

renamed as (

    select
        quote || '-' || cast(rate_date as varchar) as rate_id,
        rate_date,
        base as base_currency,
        quote as quote_currency,
        rate as eur_rate,
        _dlt_load_id as dlt_load_id
    from source

)

select * from renamed
