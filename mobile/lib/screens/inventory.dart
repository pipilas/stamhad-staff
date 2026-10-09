import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models.dart';
import '../session.dart';
import '../theme.dart';
import '../util.dart';
import '../widgets/common.dart';

final _when = DateFormat('EEE MMM d, h:mm a');
String whenText(DateTime? d) => d == null ? 'just now' : _when.format(d);
String qtyText(num q) => q == q.roundToDouble() ? q.toInt().toString() : q.toString();

class InventoryScreen extends StatelessWidget {
  const InventoryScreen({super.key});
  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    return DefaultTabController(
      length: s.isManager ? 3 : 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Inventory'),
          bottom: TabBar(tabs: [
            const Tab(text: 'Items'),
            Tab(child: _CartTabLabel()),
            if (s.isManager) const Tab(text: 'Past orders'),
          ]),
        ),
        body: TabBarView(children: [
          const _ItemsTab(),
          const _CartTab(),
          if (s.isManager) const _OrdersTab(),
        ]),
      ),
    );
  }
}

class _CartTabLabel extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    return StreamBuilder<QuerySnapshot<Json>>(
      stream: s.col('cart').snapshots(),
      builder: (c, snap) {
        final n = snap.data?.docs.map((d) => d.data()['itemId']).toSet().length ?? 0;
        return Badge(isLabelVisible: n > 0, label: Text('$n'), offset: const Offset(14, -4), child: const Text('Order list'));
      },
    );
  }
}

// ── Items ────────────────────────────────────────────────────────────────────
class _ItemsTab extends StatefulWidget {
  const _ItemsTab();
  @override
  State<_ItemsTab> createState() => _ItemsTabState();
}

class _ItemsTabState extends State<_ItemsTab> {
  String _q = '';

  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    return Scaffold(
      floatingActionButton: s.canAddInventory
          ? FloatingActionButton.extended(
              heroTag: 'newitem',
              onPressed: () => openItemEditor(context),
              icon: const Icon(Icons.add),
              label: const Text('New item'),
            )
          : null,
      body: Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 10, 16, 4),
          child: TextField(
            decoration: const InputDecoration(prefixIcon: Icon(Icons.search), hintText: 'Search items', isDense: true),
            onChanged: (v) => setState(() => _q = v.trim().toLowerCase()),
          ),
        ),
        if (!s.canAddInventory)
          const Padding(
            padding: EdgeInsets.fromLTRB(20, 4, 20, 0),
            child: Text('You can look, but adding to the order list is turned off for you. Ask a manager.',
                style: TextStyle(color: kFgSec)),
          ),
        Expanded(
          child: StreamBuilder<QuerySnapshot<Json>>(
            stream: s.col('items').snapshots(),
            builder: (c, snap) {
              if (snap.hasError) return Empty(Icons.error_outline, 'Couldn\'t load items', friendlyError(snap.error!));
              if (!snap.hasData) return const Center(child: CircularProgressIndicator());
              final words = _q.split(' ').where((w) => w.isNotEmpty);
              final items = snap.data!.docs.map(Item.from).where((i) => i.active).where((i) {
                final hay = '${i.name} ${i.category} ${i.website}'.toLowerCase();
                return words.every(hay.contains);
              }).toList()
                ..sort((a, b) {
                  final ca = a.category.isEmpty ? '~' : a.category.toLowerCase();
                  final cb = b.category.isEmpty ? '~' : b.category.toLowerCase();
                  final o = ca.compareTo(cb);
                  return o != 0 ? o : a.name.toLowerCase().compareTo(b.name.toLowerCase());
                });
              if (items.isEmpty) {
                return Empty(Icons.inventory_2_outlined, _q.isEmpty ? 'No items yet' : 'Nothing matches "$_q"',
                    s.canAddInventory && _q.isEmpty ? 'Tap + New item to add the first one.' : '');
              }
              return StreamBuilder<QuerySnapshot<Json>>(
                stream: s.col('cart').snapshots(),
                builder: (c, cartSnap) {
                  final inCart = <String, num>{};
                  for (final d in cartSnap.data?.docs ?? const []) {
                    final l = CartLine.from(d);
                    inCart[l.itemId] = (inCart[l.itemId] ?? 0) + l.qty;
                  }
                  final rows = <Widget>[];
                  String? cat;
                  for (final i in items) {
                    final ic = i.category.isEmpty ? 'Other' : i.category;
                    if (ic != cat) {
                      cat = ic;
                      rows.add(SectionHeader(ic));
                    }
                    final n = inCart[i.id];
                    rows.add(Card(
                      child: ListTile(
                        title: Text(i.name, style: const TextStyle(fontWeight: FontWeight.w600)),
                        subtitle: Text([
                          if (i.unit.isNotEmpty) i.unit,
                          if (i.website.isNotEmpty) i.website,
                          if (n != null) '${qtyText(n)} on the order list',
                        ].join(' · ')),
                        onTap: s.isManager ? () => openItemEditor(context, item: i) : null,
                        trailing: s.canAddInventory
                            ? IconButton.filledTonal(
                                icon: const Icon(Icons.add_shopping_cart),
                                tooltip: 'Add to order list',
                                onPressed: () => addToOrder(context, i),
                              )
                            : null,
                      ),
                    ));
                  }
                  rows.add(const SizedBox(height: 96));
                  return ListView(children: rows);
                },
              );
            },
          ),
        ),
      ]),
    );
  }
}

Future<void> addToOrder(BuildContext context, Item item) async {
  final s = SessionScope.read(context);
  var qty = 1.0;
  final note = TextEditingController();
  final ok = await showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (c) => StatefulBuilder(
      builder: (c, set) => Padding(
        padding: EdgeInsets.fromLTRB(20, 0, 20, MediaQuery.of(c).viewInsets.bottom + 20),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text(item.name, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
          if (item.unit.isNotEmpty) Text(item.unit, style: const TextStyle(color: kFgSec)),
          const SizedBox(height: 16),
          Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            IconButton.filledTonal(
                iconSize: 28, onPressed: qty > 1 ? () => set(() => qty -= 1) : null, icon: const Icon(Icons.remove)),
            SizedBox(
              width: 90,
              child: Text(qtyText(qty),
                  textAlign: TextAlign.center, style: const TextStyle(fontSize: 34, fontWeight: FontWeight.w800)),
            ),
            IconButton.filledTonal(iconSize: 28, onPressed: () => set(() => qty += 1), icon: const Icon(Icons.add)),
          ]),
          const SizedBox(height: 16),
          TextField(
            controller: note,
            textCapitalization: TextCapitalization.sentences,
            decoration: const InputDecoration(labelText: 'Note (optional)', hintText: 'e.g. we\'re out, need by Friday'),
          ),
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: () => Navigator.pop(c, true),
            icon: const Icon(Icons.add_shopping_cart),
            label: const Text('Add to order list'),
          ),
        ]),
      ),
    ),
  );
  if (ok != true) return;
  try {
    await s.col('cart').add({
      'itemId': item.id,
      'itemName': item.name,
      'unit': item.unit,
      'qty': qty,
      'note': note.text.trim(),
      'byUid': s.uid,
      'byName': s.name,
      'at': FieldValue.serverTimestamp(),
    });
    if (context.mounted) toast(context, 'Added ${qtyText(qty)} × ${item.name}');
  } catch (e) {
    if (context.mounted) toast(context, friendlyError(e), error: true);
  }
}

Future<void> openItemEditor(BuildContext context, {Item? item}) {
  return Navigator.of(context).push(MaterialPageRoute(fullscreenDialog: true, builder: (_) => _ItemEditor(item: item)));
}

class _ItemEditor extends StatefulWidget {
  const _ItemEditor({this.item});
  final Item? item;
  @override
  State<_ItemEditor> createState() => _ItemEditorState();
}

class _ItemEditorState extends State<_ItemEditor> {
  late final _name = TextEditingController(text: widget.item?.name);
  late final _unit = TextEditingController(text: widget.item?.unit);
  late final _cat = TextEditingController(text: widget.item?.category);
  late final _site = TextEditingController(text: widget.item?.website);
  late final _link = TextEditingController(text: widget.item?.link);
  late final _notes = TextEditingController(text: widget.item?.notes);

  Future<void> _save() async {
    final s = SessionScope.read(context);
    if (_name.text.trim().isEmpty) {
      toast(context, 'Give the item a name.', error: true);
      return;
    }
    final data = {
      'name': _name.text.trim(),
      'unit': _unit.text.trim(),
      'category': _cat.text.trim(),
      'website': _site.text.trim(),
      'link': _link.text.trim(),
      'notes': _notes.text.trim(),
      'active': true,
      'updatedBy': s.name,
      'updatedAt': FieldValue.serverTimestamp(),
    };
    try {
      if (widget.item == null) {
        await s.col('items').add({...data, 'createdBy': s.name});
      } else {
        await s.col('items').doc(widget.item!.id).set(data, SetOptions(merge: true));
      }
      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) toast(context, friendlyError(e), error: true);
    }
  }

  Future<void> _remove() async {
    final s = SessionScope.read(context);
    final go = await confirm(context, 'Remove ${widget.item!.name}?', 'Past orders keep their record.',
        yes: 'Remove', danger: true);
    if (!go) return;
    try {
      await s.col('items').doc(widget.item!.id).update({'active': false});
      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) toast(context, friendlyError(e), error: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    Widget f(TextEditingController c, String label, {TextInputType? kb}) => Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: TextField(controller: c, keyboardType: kb, decoration: InputDecoration(labelText: label)),
        );
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.item == null ? 'New item' : 'Edit item'),
        actions: [
          if (widget.item != null && s.isManager)
            IconButton(onPressed: _remove, icon: const Icon(Icons.delete_outline, color: kDanger)),
        ],
      ),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        f(_name, 'Name'),
        f(_unit, 'Unit / size (e.g. case of 24, 750 ml)'),
        f(_cat, 'Category (e.g. Bar, Kitchen, Cleaning)'),
        f(_site, 'Where to buy (e.g. Restaurant Depot)'),
        f(_link, 'Link (optional)', kb: TextInputType.url),
        f(_notes, 'Notes'),
        const SizedBox(height: 8),
        FilledButton(onPressed: _save, child: const Text('Save')),
      ]),
    );
  }
}

// ── Order list (who added what) ───────────────────────────────────────────────
class _CartTab extends StatelessWidget {
  const _CartTab();

  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    return StreamBuilder<QuerySnapshot<Json>>(
      stream: s.col('cart').snapshots(),
      builder: (c, snap) {
        if (snap.hasError) return Empty(Icons.error_outline, 'Couldn\'t load the order list', friendlyError(snap.error!));
        if (!snap.hasData) return const Center(child: CircularProgressIndicator());
        final lines = snap.data!.docs.map(CartLine.from).toList();
        if (lines.isEmpty) {
          return const Empty(Icons.shopping_cart_outlined, 'The order list is empty',
              'Items people add show up here with their name.');
        }
        final groups = <String, List<CartLine>>{};
        for (final l in lines) {
          groups.putIfAbsent(l.itemId, () => []).add(l);
        }
        final keys = groups.keys.toList()
          ..sort((a, b) => groups[a]!.first.itemName.toLowerCase().compareTo(groups[b]!.first.itemName.toLowerCase()));
        return Column(children: [
          Expanded(
            child: ListView(padding: const EdgeInsets.only(top: 8, bottom: 16), children: [
              for (final k in keys) _CartGroup(lines: groups[k]!..sort((a, b) => (a.at ?? DateTime.now()).compareTo(b.at ?? DateTime.now()))),
            ]),
          ),
          if (s.isManager)
            SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 4, 16, 12),
                child: SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: () => _placeOrder(context, groups),
                    icon: const Icon(Icons.check),
                    label: Text('Mark ${keys.length} item${keys.length == 1 ? '' : 's'} as ordered'),
                  ),
                ),
              ),
            ),
        ]);
      },
    );
  }

  Future<void> _placeOrder(BuildContext context, Map<String, List<CartLine>> groups) async {
    final s = SessionScope.read(context);
    final go = await confirm(context, 'Mark as ordered?',
        'The order list is saved in Past orders (with who added what) and then cleared.',
        yes: 'Mark as ordered');
    if (!go) return;
    try {
      final b = s.db.batch();
      final lines = [
        for (final g in groups.values)
          {
            'itemId': g.first.itemId,
            'name': g.first.itemName,
            'unit': g.first.unit,
            'qty': g.fold<num>(0, (a, l) => a + l.qty),
            'entries': [for (final l in g) l.toOrderEntry()],
          }
      ];
      b.set(s.col('orders').doc(), {
        'date': ymd(DateTime.now()),
        'at': FieldValue.serverTimestamp(),
        'byUid': s.uid,
        'byName': s.name,
        'lines': lines,
      });
      for (final g in groups.values) {
        for (final l in g) {
          b.delete(s.col('cart').doc(l.id));
        }
      }
      await b.commit();
      if (context.mounted) toast(context, 'Saved in Past orders.');
    } catch (e) {
      if (context.mounted) toast(context, friendlyError(e), error: true);
    }
  }
}

class _CartGroup extends StatelessWidget {
  const _CartGroup({required this.lines});
  final List<CartLine> lines;

  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    final total = lines.fold<num>(0, (a, l) => a + l.qty);
    final first = lines.first;
    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 8, 8),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(
              child: Text(first.itemName, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
            ),
            Text('${qtyText(total)}${first.unit.isNotEmpty ? ' × ${first.unit}' : ''}',
                style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: kAccent)),
            const SizedBox(width: 8),
          ]),
          const SizedBox(height: 4),
          for (final l in lines)
            Row(children: [
              const Icon(Icons.subdirectory_arrow_right, size: 16, color: kFgSec),
              const SizedBox(width: 4),
              Expanded(
                child: Text(
                  '+${qtyText(l.qty)} by ${l.byUid == s.uid ? 'you' : l.byName} · ${whenText(l.at)}'
                  '${l.note.isNotEmpty ? '\n“${l.note}”' : ''}',
                  style: const TextStyle(color: kFgSec, fontSize: 13),
                ),
              ),
              if (s.isManager || l.byUid == s.uid)
                IconButton(
                  visualDensity: VisualDensity.compact,
                  icon: const Icon(Icons.close, size: 18),
                  tooltip: 'Remove',
                  onPressed: () async {
                    try {
                      await s.col('cart').doc(l.id).delete();
                    } catch (e) {
                      if (context.mounted) toast(context, friendlyError(e), error: true);
                    }
                  },
                ),
            ]),
        ]),
      ),
    );
  }
}

// ── Past orders ───────────────────────────────────────────────────────────────
class _OrdersTab extends StatelessWidget {
  const _OrdersTab();
  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    return StreamBuilder<QuerySnapshot<Json>>(
      stream: s.col('orders').orderBy('date', descending: true).limit(40).snapshots(),
      builder: (c, snap) {
        if (snap.hasError) return Empty(Icons.error_outline, 'Couldn\'t load orders', friendlyError(snap.error!));
        if (!snap.hasData) return const Center(child: CircularProgressIndicator());
        final orders = snap.data!.docs.map(PastOrder.from).toList();
        if (orders.isEmpty) return const Empty(Icons.receipt_long_outlined, 'No orders yet');
        return ListView(padding: const EdgeInsets.only(top: 8, bottom: 24), children: [
          for (final o in orders)
            Card(
              child: ExpansionTile(
                shape: const Border(),
                title: Text(o.date.isEmpty ? 'Order' : shortDay(parseYmd(o.date)),
                    style: const TextStyle(fontWeight: FontWeight.w700)),
                subtitle: Text('${o.lines.length} item${o.lines.length == 1 ? '' : 's'} · marked by ${o.byName}'),
                children: [
                  for (final l in o.lines)
                    ListTile(
                      dense: true,
                      title: Text('${l['name']}  ×${qtyText((l['qty'] ?? 0) as num)}'),
                      subtitle: Text([
                        for (final e in (l['entries'] as List? ?? []))
                          '+${qtyText(((e as Map)['qty'] ?? 0) as num)} ${e['byName']}'
                              '${e['at'] is Timestamp ? ' (${whenText((e['at'] as Timestamp).toDate())})' : ''}'
                      ].join('\n')),
                    ),
                ],
              ),
            ),
        ]);
      },
    );
  }
}
