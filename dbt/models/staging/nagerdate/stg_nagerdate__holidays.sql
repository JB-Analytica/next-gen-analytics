with source as (

    select * from {{ source('nagerdate', 'holidays') }}

),

renamed as (

    select
        _dlt_id as holiday_id,
        country_code,
        date as holiday_date,
        local_name as holiday_local_name,
        name as holiday_name,
        is_fixed,
        is_global,
        _dlt_load_id as dlt_load_id
    from source

)

select * from renamed
