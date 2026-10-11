# 3Dプリント用STL

外枠系と回転部系を、1部品ずつSTLに分けています。

## 外枠系

- `capsule_dispenser_outer_housing.stl`
- `capsule_dispenser_outer_front_plate.stl`
- `capsule_dispenser_outer_rear_plate.stl`
- `capsule_dispenser_outer_hopper_adapter.stl`
- `capsule_dispenser_outer_outlet_adapter.stl`

## 回転部系

- `capsule_dispenser_rotor_body.stl`
- `capsule_dispenser_rotor_lid.stl`

回転部は、大きなブリッジを避けるため本体と後ろ蓋を別々に印刷し、M3ねじ4本で組み立てます。

既定寸法は65 mmカプセル用です。外枠の最大XY寸法は156 mm、回転部の最大直径は146 mmです。スカートやブリムを含めると160 mmを超える可能性があるため、スライサー上でも造形範囲を確認してください。
