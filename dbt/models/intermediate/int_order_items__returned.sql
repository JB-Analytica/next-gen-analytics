-- A line is returned at most once (align_source guarantees it and fct_returns tests it). The
-- collapse stays as a guard so a real source with repeat events cannot double-count a line.
select
    order_item_id,
    count(*) as return_count,
    min(returned_at) as first_returned_at
from {{ ref('stg_noordkust__returns') }}
group by order_item_id
