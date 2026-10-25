#!/usr/bin/env python3
"""Mininet/OVS admission enforcement experiment. Real emulated packets, configured-capacity refresh."""
import argparse,csv,json,os,subprocess,sys,time,platform
from pathlib import Path
from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.link import TCLink
from mininet.log import setLogLevel
from controller import Coordinator,Observation

def cmd(*args):
    p=subprocess.run(args,text=True,capture_output=True)
    if p.returncode: raise RuntimeError(f'{args}: {p.stderr}')
    return p.stdout

def trial(policy,scenario,repeat,args,out):
    rate=4 if 'underload' in scenario else 6
    age=30 if 'stale' in scenario else 1
    cap=args.capacity
    reported=cap if 'underload' in scenario or 'fresh' in scenario else 14
    net=Mininet(controller=None,switch=OVSSwitch,link=TCLink,autoSetMacs=True)
    h1=net.addHost('h1',ip='10.0.0.1/24');h2=net.addHost('h2',ip='10.0.0.2/24');h3=net.addHost('h3',ip='10.0.0.3/24')
    s1=net.addSwitch('s1',failMode='standalone');s2=net.addSwitch('s2',failMode='standalone')
    net.addLink(h1,s1,bw=20,delay='2ms');net.addLink(h3,s1,bw=20,delay='2ms')
    net.addLink(s1,s2,bw=cap,delay='10ms');net.addLink(s2,h2,bw=20,delay='2ms')
    procs=[]
    try:
        net.start()
        if ' 0% packet loss' not in h1.cmd('ping -c 2 -W 2 10.0.0.2'):
            raise RuntimeError('Connectivity failed')
        # This is a configured-capacity refresh, NOT live available-bandwidth telemetry.
        clock=time.monotonic
        coord=Coordinator(rate,max_age_s=5,clock=clock,refresh=lambda:Observation(cap,clock(),2))
        coord.update(Observation(reported,clock()-age,1))
        start=time.perf_counter()
        if policy=='independent':admit=True;reason='uncoordinated'
        elif policy=='stale_capacity':admit=2*rate<=reported;reason='reported_capacity'
        elif policy=='freshness_guard':admit=age<=5 and 2*rate<=reported;reason='freshness_guard'
        elif policy=='safe_loop':
            decision=coord.admit('candidate',rate)
            admit=decision.admitted;reason=decision.reason
        else:raise ValueError(policy)
        decision_ms=(time.perf_counter()-start)*1000
        # All candidate senders run, including rejected ones. OVS must enforce rejection.
        if not admit:
            cmd('ovs-ofctl','add-flow','s1','priority=300,ip,nw_src=10.0.0.3,actions=drop')
            flows=cmd('ovs-ofctl','dump-flows','s1')
            if 'nw_src=10.0.0.3' not in flows or 'actions=drop' not in flows:
                raise RuntimeError('OVS drop rule not confirmed')
        # Launch packet receivers in the destination namespace, and both senders.
        # UDP payload contains 8-byte sequence and padding; fixed 1200 bytes.
        receiver_code='''import socket,json,sys,time\nport=int(sys.argv[1]);dur=float(sys.argv[2]);sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.bind(("0.0.0.0",port));sock.settimeout(.25);count=0;total=0;start=time.monotonic();last=start\nwhile time.monotonic()-start<dur:\n try:\n  d,a=sock.recvfrom(65535);count+=1;total+=len(d);last=time.monotonic()\n except socket.timeout:pass\nprint(json.dumps({"packets_received":count,"payload_bytes_received":total,"window_seconds":dur,"last_packet_elapsed_s":last-start}),flush=True)'''
        sender_code='''import socket,sys,time,struct\nport=int(sys.argv[1]);rate=float(sys.argv[2]);duration=float(sys.argv[3]);sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);size=1200;interval=size*8/(rate*1000000);start=time.monotonic();n=0;payload=b"x"*(size-8)\nwhile True:\n target=start+n*interval;now=time.monotonic()\n if now-start>=duration:break\n if target>now:time.sleep(min(target-now,.01));continue\n sock.sendto(struct.pack("!Q",n)+payload,("10.0.0.2",port));n+=1\nprint(n,flush=True)'''
        rec={};send={}
        for label,port in [('background',5201),('candidate',5202)]:
            p=h2.popen([sys.executable,'-u','-c',receiver_code,str(port),str(args.seconds+2)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            procs.append(p);rec[label]=p
        time.sleep(.5)
        for label,host,port in [('background',h1,5201),('candidate',h3,5202)]:
            p=host.popen([sys.executable,'-u','-c',sender_code,str(port),str(rate),str(args.seconds)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            procs.append(p);send[label]=p
        sent={}
        for label,p in send.items():
            stdout,stderr=p.communicate(timeout=args.seconds+20)
            if p.returncode:raise RuntimeError(f'{label} sender: {stderr}')
            sent[label]=int(stdout.strip())
        received={}
        for label,p in rec.items():
            stdout,stderr=p.communicate(timeout=args.seconds+20)
            if p.returncode:raise RuntimeError(f'{label} receiver: {stderr}')
            received[label]=json.loads(stdout)
        # Packet loss estimates are valid only if every sent datagram is accounted for in the receiver window.
        row={'policy':policy,'scenario':scenario,'trial':repeat,'rate_mbps':rate,'capacity_mbps':cap,'reported_capacity_mbps':reported,'telemetry_age_s':age,'candidate_admitted':admit,'decision_reason':reason,'decision_ms':round(decision_ms,5)}
        for label in ('background','candidate'):
            n=received[label]['packets_received'];bytes_=received[label]['payload_bytes_received'];tx=sent[label]
            if n>tx:raise RuntimeError('Receiver count exceeds sender count')
            row[f'{label}_tx_packets']=tx;row[f'{label}_rx_packets']=n
            row[f'{label}_loss_pct']=round(100*(tx-n)/tx,4) if tx else None
            row[f'{label}_payload_mbps']=round(bytes_*8/(args.seconds*1e6),4)
        row['aggregate_payload_mbps']=round(row['background_payload_mbps']+row['candidate_payload_mbps'],4)
        row['ovs_drop_packets']=None
        if not admit:
            flows=cmd('ovs-ofctl','dump-flows','s1')
            for line in flows.splitlines():
                if 'nw_src=10.0.0.3' in line and 'actions=drop' in line:
                    import re
                    m=re.search(r'n_packets=(\d+)',line)
                    if m:row['ovs_drop_packets']=int(m.group(1))
            if row['ovs_drop_packets'] is None:raise RuntimeError('Drop counter unavailable')
        (out/f'{scenario}_{policy}_{repeat:02d}.json').write_text(json.dumps({'metrics':row,'receiver_reports':received},indent=2))
        print(json.dumps(row),flush=True)
        return row
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()
                try:p.communicate(timeout=2)
                except subprocess.TimeoutExpired:p.kill();p.communicate()
        net.stop()

def main():
    p=argparse.ArgumentParser();p.add_argument('--repeats',type=int,default=3);p.add_argument('--seconds',type=int,default=8);p.add_argument('--capacity',type=float,default=10);p.add_argument('--output',default='integrated_results');args=p.parse_args()
    if args.repeats<1 or args.seconds<3 or args.capacity<=0:p.error('invalid arguments')
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    (out/'metadata.json').write_text(json.dumps({'host':platform.platform(),'python':sys.version,'seconds':args.seconds,'capacity_mbps':args.capacity,'notes':'Mininet emulation; configured-capacity refresh; UDP application-layer receiver packet counts; candidate traffic always generated; OVS drop enforcement'},indent=2))
    scenarios=['fresh_underload','stale_underload','fresh_overload','stale_overload']
    policies=['independent','stale_capacity','freshness_guard','safe_loop']
    import random
    rng=random.Random(20261024)
    tasks=[(s,p,i) for i in range(1,args.repeats+1) for s in scenarios for p in policies]
    rng.shuffle(tasks)
    with (out/'summary.csv').open('w',newline='') as f:
        writer=None
        for j,(s,p,i) in enumerate(tasks,1):
            row=trial(p,s,i,args,out)
            if writer is None:writer=csv.DictWriter(f,fieldnames=list(row));writer.writeheader()
            writer.writerow(row);f.flush();os.fsync(f.fileno())
            print(f'Completed {j}/{len(tasks)}',flush=True)
if __name__=='__main__':setLogLevel('warning');main()
