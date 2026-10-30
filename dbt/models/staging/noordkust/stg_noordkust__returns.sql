with source as (

    select * from {{ source('noordkust', 'returns') }}

),

renamed as (

    select
        id as return_id,
        order_item_id,
        reason as return_reason,
        returned_at,
        created_at,
        updated_at,
        _dlt_load_id as dlt_load_id
    from source

)

select * from renamed
