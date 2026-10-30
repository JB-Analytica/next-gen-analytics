{#- The source's own money must be internally consistent, exactly, in minor units: an order's
    subtotal is the sum of its lines and its total is the subtotal plus shipping. If this fails
    the generator (or a real source) is wrong, not the marts. -#}

with lines as (

    select
        order_id,
        sum(net_minor) as lines_minor
    from {{ ref('int_order_items__priced') }}
    group by order_id

)

select
    orders.order_id,
    orders.subtotal_minor,
    lines.lines_minor,
    orders.total_minor,
    orders.shipping_minor
from {{ ref('stg_noordkust__orders') }} as orders
left join lines on orders.order_id = lines.order_id
where orders.subtotal_minor != coalesce(lines.lines_minor, 0)
    or orders.total_minor != orders.subtotal_minor + orders.shipping_minor
