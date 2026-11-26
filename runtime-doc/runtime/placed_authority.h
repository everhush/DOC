#ifndef DOC_PLACED_AUTHORITY_H
#define DOC_PLACED_AUTHORITY_H
/* One declared surviving source authority, using the exact bundled-source
 * checkpoint schema. Only acknowledged durable facts are recoverable.
 * No external effects, replicas, elections or cross-process consensus. */
static size_t *placed_no_carry(const Epoch *e){size_t *carry=zalloc(e->n,sizeof(*carry));if(carry)for(size_t i=0;i<e->n;i++)carry[i]=e->n;return carry;}
static int placed_authority_save(Epoch *e,const char *path){
#ifndef DOC_SOURCE_SHA256
    (void)e;(void)path;return 0;
#else
    if(!e->placed||e->in_flight||e->committed<=0||!path||!checkpoint_enabled())return 0;
    size_t *carry=placed_no_carry(e);if(!carry)return 0;
    uint64_t receipt=0;e->placed->durable_epoch=0;e->placed->durable_checksum=0;
    int ok=checkpoint_save_record(e,carry,(uint64_t)e->committed,path,&receipt);free(carry);
    if(ok){char name[257];int dir=output_parent(path,name);if(dir<0)return 0;ok=!fsync(dir);close(dir);}
    if(ok){e->placed->durable_epoch=e->committed;e->placed->durable_checksum=receipt;}return ok;
#endif
}
static int placed_authority_restore(Epoch *e,const char *path){
#ifndef DOC_SOURCE_SHA256
    (void)e;(void)path;return 0;
#else
    if(!e->placed||e->in_flight||e->committed||e->placed->durable_epoch<=0||!path||!checkpoint_enabled())return 0;
    Region owner={0};uint64_t saved=0;size_t target;int ok=0;
    size_t *carry=placed_no_carry(e);V *values=zalloc(e->n,sizeof(*values));
    if(!carry||!values||!checkpoint_load_record(e,carry,path,&owner,values,&saved,&e->placed->durable_checksum)||saved!=(uint64_t)e->placed->durable_epoch||saved>=INT64_MAX)goto done;
    if((int64_t)saved>e->attempt)e->attempt=(int64_t)saved;
    if(!epoch_begin(e))goto done;ok=1;
    for(size_t i=0;i<e->n&&ok;i++)if(e->states[i].role==1){
        Cell *c=e->cell+i;ok=store_value(&c->candidate,&c->result,values[i]);if(ok)publish_private(e,i);
    }
    if(ok)ok=batch(e,0,NULL,&target);
    ok=epoch_finish(e,ok);
done:clear(&owner);free(values);free(carry);return ok;
#endif
}
/* Coordinator-only observation: return an available immutable snapshot,
 * otherwise reconstruct missing derived materialization before observing.
 * Other threads use epoch_read and never start a writer. */
static int placed_observe(Epoch *e,size_t target,EpochReader visit,void *ctx){
    if(!e->placed||!visit||target>e->n||(target<e->n&&!e->states[target].name)||active||failure_target)return 0;
    if(epoch_read(e,target,visit,ctx))return 1;
    epoch_lock(e);int missing=0,open=e->in_flight,committed=e->committed>0;
    if(!open)for(size_t i=0;i<e->n;i++)if(e->states[i].name&&(target==e->n||target==i)&&(!e->have[i]||e->dirty[i]))missing=1;
    epoch_unlock(e);
    if(open||!committed||!missing||!epoch_begin(e))return 0;
    size_t full;int ok=batch(e,0,NULL,&full);if(!epoch_finish(e,ok))return 0;
    return epoch_read(e,target,visit,ctx);
}
#endif
