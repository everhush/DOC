/* Temporary Stage-0 terminal platform adapter. Game transitions, collision,
 * score, spawning, timers, radar and cue calculations come from DOC. */
#define DOC_GAME_LIMIT 65536u
typedef struct {const char *source,*derived;} doc_game_pair;
static const doc_game_pair doc_game_carries[]={
    {"frame","next_frame"},{"player_x","next_x"},{"player_y","next_y"},
    {"coin_x","next_coin_x"},{"coin_y","next_coin_y"},{"score","next_score"},
    {"paused","next_paused"},{"won","next_won"},{"animation_phase","next_animation_phase"},
    {"entity_ids","next_entity_ids"},{"entity_xs","next_entity_xs"},{"entity_ys","next_entity_ys"},
    {"next_entity_id","next_next_entity_id"},{"issued_high_water","next_issued_high_water"},
    {"prefab_template_xs","template_next_xs"},{"prefab_template_ys","template_next_ys"}
};
static size_t doc_game_id(const char *name){return doc_lookup(name,strlen(name));}
static int doc_game_scalar(const doc_state *s,const char *name,unsigned kind,int64_t *out){
    size_t id=doc_game_id(name);if(id==DOC_N||doc_kind[id]!=kind||s->dirty[id])return 0;
    *out=s->value[id].scalar;return 1;
}
static int doc_game_bind(size_t *carry,size_t *action){
    for(size_t i=0;i<DOC_N;i++)carry[i]=DOC_N;
    for(size_t i=0;i<sizeof(doc_game_carries)/sizeof(*doc_game_carries);i++){
        size_t a=doc_game_id(doc_game_carries[i].source),b=doc_game_id(doc_game_carries[i].derived);
        if(i>=9&&a==DOC_N&&b==DOC_N)continue;
        if(a==DOC_N||b==DOC_N||!doc_source[a]||doc_source[b]||doc_kind[a]!=doc_kind[b])
            return doc_fail("invalid game carry layout");
        carry[a]=b;
    }
    *action=doc_game_id("action");
    if(*action==DOC_N||!doc_source[*action]||doc_kind[*action]!=DOC_INT||carry[*action]!=DOC_N)
        return doc_fail("invalid game action source");
    return 1;
}
static int doc_game_present(const doc_state *s,int headless){
    int64_t frame,x,y,cx,cy,score,paused,won,width,height,wx,wy,radar_p=0,radar_c=0;
#define GAME_FIELD(name,target,kind) if(!doc_game_scalar(s,name,kind,&target))return doc_fail("invalid game presentation field " name)
    GAME_FIELD("next_frame",frame,DOC_INT);GAME_FIELD("next_x",x,DOC_INT);GAME_FIELD("next_y",y,DOC_INT);
    GAME_FIELD("next_coin_x",cx,DOC_INT);GAME_FIELD("next_coin_y",cy,DOC_INT);GAME_FIELD("next_score",score,DOC_INT);
    GAME_FIELD("next_paused",paused,DOC_BOOL);GAME_FIELD("next_won",won,DOC_BOOL);
    GAME_FIELD("width",width,DOC_INT);GAME_FIELD("height",height,DOC_INT);
    GAME_FIELD("wall_x",wx,DOC_INT);GAME_FIELD("wall_y",wy,DOC_INT);
    if(width<1||width>200||height<1||height>200)return doc_fail("game screen outside terminal budget");
    size_t ix=doc_game_id("next_entity_xs"),iy=doc_game_id("next_entity_ys"),ii=doc_game_id("next_entity_ids");
    int entities=ix!=DOC_N||iy!=DOC_N||ii!=DOC_N;doc_value xs={0},ys={0},ids={0};
    if(entities){
        if(ix==DOC_N||iy==DOC_N||ii==DOC_N||doc_kind[ix]!=DOC_LIST||doc_kind[iy]!=DOC_LIST||doc_kind[ii]!=DOC_LIST||
           s->dirty[ix]||s->dirty[iy]||s->dirty[ii])return doc_fail("invalid game entity columns");
        xs=s->value[ix];ys=s->value[iy];ids=s->value[ii];
        if(xs.len!=ys.len||xs.len!=ids.len)return doc_fail("game entity columns misaligned");
    }
    int radar=doc_game_id("radar_player_cell")!=DOC_N||doc_game_id("radar_coin_cell")!=DOC_N;
    if(radar){GAME_FIELD("radar_player_cell",radar_p,DOC_INT);GAME_FIELD("radar_coin_cell",radar_c,DOC_INT);}
#undef GAME_FIELD
    printf("DOC_GAME_FRAME: tick=%" PRId64 " player=(%" PRId64 ",%" PRId64 ") score=%" PRId64 " paused=%s won=%s coin=(%" PRId64 ",%" PRId64 ")\n",frame,x,y,score,paused?"true":"false",won?"true":"false",cx,cy);
    if(entities){
        printf("DOC_GAME_ENTITIES: count=%zu ids=[",ids.len);
        for(size_t i=0;i<ids.len;i++)printf("%s%" PRId64,i?", ":"",ids.data[i]);
        printf("] hazards=[");
        for(size_t i=0;i<ids.len;i++)printf("%s(%" PRId64 ", %" PRId64 ")",i?", ":"",xs.data[i],ys.data[i]);
        printf("]\n");
    }
    if(radar)printf("DOC_GAME_RADAR: pre_action_player_cell=%" PRId64 " pre_action_coin_cell=%" PRId64 "\n",radar_p,radar_c);
    if(!headless){
        for(int64_t row=0;row<height;row++){
            for(int64_t col=0;col<width;col++){
                char pixel='.';int obstacle=0;
                for(size_t i=0;i<ids.len;i++)if(xs.data[i]==col&&ys.data[i]==row){obstacle=1;break;}
                if(col==x&&row==y)pixel='@';
                else if(col==wx&&row==wy)pixel='#';
                else if(obstacle)pixel='X';
                else if(col==cx&&row==cy&&!won)pixel='*';
                putchar(pixel);
            }putchar('\n');
        }
        if(won)puts("GOAL REACHED — press r to restart or q to quit");
    }
    fflush(stdout);return 1;
}
static int doc_game_input(unsigned char c,int64_t *action){
    switch(c){
        case '.':*action=0;return 1;case 'w':*action=1;return 1;case 's':*action=2;return 1;
        case 'a':*action=3;return 1;case 'd':*action=4;return 1;case 'p':*action=5;return 1;
        case 'r':*action=6;return 1;case 'e':*action=7;return 1;case 'x':*action=8;return 1;
        case 'q':return 0;default:return -1;
    }
}
static int doc_game_advance(doc_state *s,const size_t *carry,size_t action,int64_t code){
    doc_state candidate;if(!doc_reset(&candidate))return 0;
    int ok=1;
    for(size_t i=0;i<DOC_N&&ok;i++)if(carry[i]!=DOC_N)ok=doc_assign(&candidate,i,s->value[carry[i]]);
    if(ok)ok=doc_assign(&candidate,action,(doc_value){.kind=DOC_INT,.scalar=code});
    if(!ok||!doc_stabilize(&candidate,DOC_N)){doc_state_drop(&candidate);return 0;}
    doc_state_drop(s);*s=candidate;doc_memory_report("commit");return 1;
}
/* Bounded post-stabilization PCM WAV effect, atomic per file. */
static int doc_game_safe_path(const char *p){
    size_t total=strlen(p);if(!total||total>200)return 0;
    const char *start=p;
    for(;;p++){
        unsigned char c=(unsigned char)*p;
        if(!c||c=='/'){
            size_t n=(size_t)(p-start);
            if(!n||(n==1&&*start=='.')||(n==2&&start[0]=='.'&&start[1]=='.'))return 0;
            if(!c)return 1;start=p+1;
        }else if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'||c=='-'||c=='.'))return 0;
    }
}
static int doc_game_write(int fd,const unsigned char *p,size_t n){
    while(n){
        ssize_t k=write(fd,p,n);
        if(k<0&&errno==EINTR)continue;
        if(k<=0)return 0;p+=k;n-=(size_t)k;
    }return 1;
}
static void doc_game_le16(unsigned char *p,uint16_t x){p[0]=(unsigned char)x;p[1]=(unsigned char)(x>>8);}
static void doc_game_le32(unsigned char *p,uint32_t x){for(unsigned i=0;i<4;i++)p[i]=(unsigned char)(x>>(8*i));}
static int doc_game_audio(const doc_state *s,int dir,const char *path,uint64_t epoch){
    if(dir<0)return 1;
    int64_t hz,ms;
    if(!doc_game_scalar(s,"audio_hz",DOC_INT,&hz)||!doc_game_scalar(s,"audio_ms",DOC_INT,&ms))return doc_fail("invalid DOC audio fields");
    if(!hz&&!ms)return 1;
    if(hz<20||hz>20000||ms<1||ms>5000)return doc_fail("DOC audio cue out of bounds");
    char name[64],temp[100];snprintf(name,sizeof(name),"cue_%" PRIu64 ".wav",epoch);
    snprintf(temp,sizeof(temp),".doc-audio-%ld-%s.tmp",(long)getpid(),name);
    int fd=openat(dir,temp,O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW,0600);
    if(fd<0)return doc_fail("audio temporary output unavailable");
    uint32_t samples=44100u*(uint32_t)ms/1000u,bytes=samples*2u;
    unsigned char header[44]={0};
    memcpy(header,"RIFF",4);doc_game_le32(header+4,bytes+36);memcpy(header+8,"WAVEfmt ",8);
    doc_game_le32(header+16,16);doc_game_le16(header+20,1);doc_game_le16(header+22,1);
    doc_game_le32(header+24,44100);doc_game_le32(header+28,88200);doc_game_le16(header+32,2);
    doc_game_le16(header+34,16);memcpy(header+36,"data",4);doc_game_le32(header+40,bytes);
    int ok=doc_game_write(fd,header,sizeof(header));unsigned char block[4096];
    for(uint32_t start=0;ok&&start<samples;){
        uint32_t count=samples-start;if(count>sizeof(block)/2)count=sizeof(block)/2;
        for(uint32_t i=0;i<count;i++){
            double radians=6.283185307179586476925286766559*(double)hz*(double)(start+i)/44100.0;
            int16_t sample=(int16_t)round(sin(radians)*7200.0);
            doc_game_le16(block+2*i,(uint16_t)sample);
        }
        ok=doc_game_write(fd,block,count*2);start+=count;
    }
    if(ok&&fsync(fd))ok=0;
    if(close(fd))ok=0;
    if(ok&&renameat(dir,temp,dir,name))ok=0;
    if(!ok){unlinkat(dir,temp,0);return doc_fail("DOC audio output failed");}
    printf("DOC_GAME_AUDIO_WAV: epoch=%" PRIu64 " path=%s/%s\n",epoch,path,name);return 1;
}
static uint64_t doc_game_clock(void){
    struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t))return 0;
    return (uint64_t)t.tv_sec*1000000u+(uint64_t)t.tv_nsec/1000u;
}
static int doc_game_compare_u64(const void *a,const void *b){
    uint64_t x=*(const uint64_t*)a,y=*(const uint64_t*)b;return (x>y)-(x<y);
}
static int doc_game_main(int argc,char **argv,int at,const char *root){
    const char *replay=NULL,*audio=NULL;int headless=0,measure=0,workers_set=0,dir=-1;
    for(;at<argc;at++){
        const char *arg=argv[at];
        if(!strncmp(arg,"--replay=",9)&&!replay)replay=arg+9;
        else if(!strncmp(arg,"--audio-dir=",12)&&!audio)audio=arg+12;
        else if(!strncmp(arg,"--workers=",10)&&!workers_set){
            uint64_t workers;if(!doc_u64(arg+10,&workers)||workers<1||setenv("DOC_WORKERS",arg+10,1))return !doc_fail("invalid workers");
            workers_set=1;
        }else if(!strcmp(arg,"--headless"))headless=1;
        else if(!strcmp(arg,"--measure"))measure=1;
        else return !doc_fail("unknown/duplicate game option (checkpoint support pending)");
    }
    if(replay&&strlen(replay)>DOC_GAME_LIMIT)return !doc_fail("game replay exceeds bounded input");
    size_t carry[DOC_N],action;if(!doc_game_bind(carry,&action))return 1;
    if(audio){
        if(!doc_game_safe_path(audio))return !doc_fail("audio output path not confined");
        int rootfd=open(root,O_RDONLY|O_DIRECTORY|O_CLOEXEC);if(rootfd<0)return !doc_fail("game root unavailable");
        dir=doc_asset_open(rootfd,audio);close(rootfd);struct stat st;
        if(dir<0||fstat(dir,&st)||!S_ISDIR(st.st_mode)){if(dir>=0)close(dir);return !doc_fail("audio directory unavailable");}
    }
    uint64_t *samples=measure?malloc(DOC_GAME_LIMIT*sizeof(*samples)):NULL;
    if(measure&&!samples){if(dir>=0)close(dir);return !doc_fail("measurement allocation failed");}
    doc_state state;int ready=doc_reset(&state),ok=ready&&doc_stabilize(&state,DOC_N);
    uint64_t epoch=0;size_t n=0;
    if(ok)ok=doc_game_present(&state,headless);
    if(!replay&&ok)puts("Controls: w/a/s/d move, p pause, r restart, e spawn, x despawn, . idle, q quit. Press Enter after input.");
    size_t position=0;
    while(ok){
        int c=replay?(unsigned char)replay[position++]:getchar();
        if(replay?!c:c==EOF)break;
        if(!replay&&isspace((unsigned char)c))continue;
        int64_t code;int admitted=doc_game_input((unsigned char)c,&code);
        if(!admitted)break;
        if(admitted<0||epoch==DOC_GAME_LIMIT){ok=doc_fail("invalid or over-budget game input");break;}
        uint64_t before=doc_game_clock();
        if(!doc_game_advance(&state,carry,action,code)){ok=0;break;}
        uint64_t after=doc_game_clock();epoch++;
        if(measure)samples[n++]=after>=before?after-before:0;
        if(!doc_game_audio(&state,dir,audio,epoch)||!doc_game_present(&state,headless)){ok=0;break;}
    }
    if(!replay&&ferror(stdin))ok=doc_fail("game input read failed");
    if(ok&&measure){
        qsort(samples,n,sizeof(*samples),doc_game_compare_u64);
        uint64_t p50=n?samples[(n*50-1)/100]:0,p95=n?samples[(n*95-1)/100]:0;
        struct rusage ru;long rss=getrusage(RUSAGE_SELF,&ru)==0?ru.ru_maxrss:0;
        printf("DOC_GAME_CPU_MEASURED: steps=%zu p50_us=%" PRIu64 " p95_us=%" PRIu64 " process_peak_rss_kib=%ld measurement=DOC_recurrence_advance_only\n",n,p50,p95,rss);
    }
    if(ready)doc_state_drop(&state);free(samples);if(dir>=0)close(dir);
    return ok?0:1;
}
