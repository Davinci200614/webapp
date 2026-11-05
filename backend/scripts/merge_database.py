"""Merge business records while preserving live conversation state and accounts."""
import argparse,hashlib,json,sqlite3
from datetime import datetime,timezone
from pathlib import Path
from app.db import backup_database
SUPPORTED=('farmers','machines','requests','employment_listings','catalog_terms','bookings')
PRIVATE=('operators','operator_sessions','schema_migrations')
def quoted(name):return '"'+name.replace('"','""')+'"'
def merge(source,target,backup_dir):
    source=Path(source).resolve();target=Path(target).resolve()
    if source==target:raise ValueError('Source and target must differ')
    src=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True);src.row_factory=sqlite3.Row
    dst=sqlite3.connect(target,timeout=30);dst.row_factory=sqlite3.Row
    report={'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'inserted':{},'already_present':{},'id_maps':{},'preserved_accounts':True}
    try:
        for conn in (src,dst):
            if conn.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('Database integrity check failed')
            if conn.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('Foreign key check failed')
        tables={r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        for table in tables-set(SUPPORTED)-set(PRIVATE):
            if src.execute('SELECT count(*) FROM '+quoted(table)).fetchone()[0]:raise ValueError('Additional nonempty source table needs mapping: '+table)
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup_dir=Path(backup_dir);backup_dir.mkdir(parents=True,exist_ok=True)
        report['backup']=str(backup_database(target,backup_dir/f'webapp-before-merge-{stamp}.db'))
        dst.execute('PRAGMA foreign_keys=ON');dst.execute('BEGIN IMMEDIATE')
        for table in SUPPORTED:
            if table not in tables:continue
            source_columns=[r[1] for r in src.execute('PRAGMA table_info('+quoted(table)+')')]
            target_columns={r[1] for r in dst.execute('PRAGMA table_info('+quoted(table)+')')}
            columns=[name for name in source_columns if name in target_columns]
            if set(source_columns)-target_columns:raise ValueError('Unsupported source columns in '+table)
            report['inserted'][table]=0;report['already_present'][table]=0
            mapping={};report['id_maps'][table]=mapping
            for row in src.execute('SELECT * FROM '+quoted(table)):
                data={name:row[name] for name in columns}
                if table=='bookings':
                    for field,domain in [('request_id','requests'),('machine_id','machines')]:data[field]=report['id_maps'][domain][str(data[field])]
                if table=='farmers':keys=['phone']
                elif table=='catalog_terms':keys=['kind','code']
                elif table=='employment_listings':keys=['owner_phone','kind']
                else:keys=[name for name in columns if name!='id']
                where=' AND '.join(quoted(name)+' IS ?' for name in keys)
                existing=dst.execute('SELECT * FROM '+quoted(table)+' WHERE '+where,[data[name] for name in keys]).fetchone()
                if existing:
                    if table in {'employment_listings','catalog_terms'} and any(existing[name]!=value for name,value in data.items() if name!='id'):raise ValueError('Conflicting identity in '+table)
                    report['already_present'][table]+=1
                    if 'id' in data:mapping[str(row['id'])]=existing['id']
                    continue
                if 'id' in data and dst.execute('SELECT 1 FROM '+quoted(table)+' WHERE id=?',(data['id'],)).fetchone():data.pop('id')
                names=list(data)
                cursor=dst.execute('INSERT INTO '+quoted(table)+' ('+','.join(map(quoted,names))+') VALUES ('+','.join('?' for _ in names)+')',[data[name] for name in names])
                if 'id' in columns:mapping[str(row['id'])]=data.get('id',cursor.lastrowid)
                report['inserted'][table]+=1
            report.setdefault('totals',{})[table]=dst.execute('SELECT count(*) FROM '+quoted(table)).fetchone()[0]
        if dst.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('Broken merged references')
        if dst.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('Merged integrity failed')
        dst.commit()
        path=backup_dir/f'merge-report-{stamp}.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        report['report']=str(path);return report
    except BaseException:dst.rollback();raise
    finally:src.close();dst.close()
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path);parser.add_argument('target',type=Path);parser.add_argument('--backup-dir',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(merge(args.source,args.target,args.backup_dir),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
