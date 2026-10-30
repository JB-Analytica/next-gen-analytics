with source as (

    select * from {{ source('noordkust', 'customers') }}

),

renamed as (

    select
        id as customer_id,
        first_name,
        last_name,
        email,
        country as country_code,
        city,
        is_marketing_opt_in,
        created_at,
        updated_at,
        _dlt_load_id as dlt_load_id
    from source

)

select * from renamed
