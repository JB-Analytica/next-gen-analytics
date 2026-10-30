with source as (

    select * from {{ source('noordkust', 'orders') }}

),

renamed as (

    select
        id as order_id,
        customer_id,
        status as order_status,
        currency,
        subtotal_minor,
        shipping_minor,
        total_minor,
        shipping_country as shipping_country_code,
        ordered_at,
        shipped_at,
        delivered_at,
        created_at,
        updated_at,
        _dlt_load_id as dlt_load_id
    from source

)

select * from renamed
