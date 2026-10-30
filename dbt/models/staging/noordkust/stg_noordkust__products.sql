with source as (

    select * from {{ source('noordkust', 'products') }}

),

renamed as (

    select
        id as product_id,
        sku,
        name as product_name,
        category,
        list_price_cents,
        is_active,
        created_at,
        updated_at,
        _dlt_load_id as dlt_load_id
    from source

)

select * from renamed
